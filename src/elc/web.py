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

**The streamed turn (A1, DEC-…77).** ``POST /api/turn_stream`` answers
``text/event-stream``: zero or more ``delta`` frames while the host thread
runs the turn, then exactly one ``final`` frame carrying the very payload
``/api/turn`` would have answered. The turn itself rides the same work
queue as ever — the handler thread only drains the turn's queue into
frames — and the deltas are the provider's own streamed increments,
forwarded **live** as they are generated (each one key-echo-checked by the
adapter before it is emitted). A provider without the optional streaming
face runs the blocking turn unchanged (zero deltas, one final), the durable
delivery keeps its default seam, and a disconnect stops the writing, never
the turn.

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
serves the conversation store's canonical user-visible window (the 50-turn
default, delivered assistant output only — the store's own §3 key rule), so
what the page recovers on load is exactly what the transcript holds; the
breadth is now also explicit on request (``?full=1`` / ``?limit=N`` — the
default window is untouched), the 主线-2 face below.

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

**主线-1 adds the settings face** — the 抽屉 · 设置 section's read and its
write, the first face that reads the rollout stage back (the 9.12-23①
preview item, closed here). ``GET /api/settings`` answers the three faces
of live truth in one payload: ``rollout_stage`` — the **effective** tier
the next turn decides under (the veto-response cut's live reading: the
coordinator's current wiring's stage when the automatic leg is assembled —
which the page's hot change moves — else the host's open-time snapshot;
``None`` stays ``None``: the fail-closed default is a fact, never a stage
this face invented); the §5.1
``TeachingPolicyProfile``'s thirteen columns when a row exists (``null``
when none does — before a first write there is nothing to read, and the
empty state says so instead of fabricating a policy; ``version`` rides
under its declared alias ``policy_version``, the spelling
``elc.user_config.types`` documents); and the §5.1 ``DisclosurePolicy``'s
four columns — the rule set read through the store's own existing read
face, the same one the controller's disclosure decision consults, so the
page shows the rules exactly as they stand with no second reading of them.
The payload also carries the three server-declared vocabularies the two
editors need (the frequency picker's four words, the eight-knob whitelist
itself, and the four §12 stage words), so the page copies no word list.
``POST /api/settings/teaching_policy`` is the knobs' write: the eight §5.1
knobs as
the full new set (``teaching_frequency`` inside the enum's own four words,
the other seven a non-empty string or ``null`` = 未配置), rebuilt around
the durable row's non-knob columns — ``version`` /
``effective_from`` are preserved verbatim, ``updated_at`` is the store's
own clock — with the version moved by :func:`_next_version` and the same
200 / 409 discipline as the goal writes. Every other key is a 400 人话
refusal: the five system columns get their own sentence, an unknown key
names itself. The write changes only how/how-often teaching is configured —
never the rollout tier, never an 开闸 face.

**The veto-response cut (user dogfood first-verification veto) makes the
tier itself page-movable** — ``POST /api/settings/mode`` takes one §12
stage word (case-sensitive, the server-declared four), persists it in
migration 0022's generic ``app_setting`` table, and swaps the coordinator's
live wiring for a new one whose ``rollout_stage`` moved
(:func:`dataclasses.replace` over the frozen dataclass — the next turn
decides under the new tier with no reassembly). The page's write is the
user's explicit tier expression — the same power as choosing the tier on
the launch command (one principal, a single-user local app); the gate
functions are untouched, and the default ``None`` still DENIES automatic
teaching. A launch command that declared a stage of its own is overridden
by the page's word from the next turn on — one principal, one live tier;
the *next* open reads the persisted word only when the launch command
declares nothing (``open_host``'s read order: explicit argument >
persisted word > ``None``), so the launch declaration keeps its role as
the per-process default.

**主线-2 adds the schedule/history-depth face** — three reads, zero writes
(调度与历史纵深：读面先行，§5.2 的调度调整是复核面，不进本刀).
``GET /api/schedule`` is the review-schedule zone's read: the Scheduler's
own classified :class:`~elc.scheduler.types.ScheduleView` at one ``as_of``
(due / overdue / upcoming buckets, the rows' own columns verbatim) — the
due decision stays where D-INV-009 put it, so a host without the scheduler
leg answers the honest ``{"available": false}`` shape instead of a raw-table
stand-in that would derive a due-ness nobody declared. ``/api/history``
gains the explicit breadth parameters (``?full=1`` / ``?limit=N``) over the
same user-visible filter family — the no-parameter answer is the unchanged
50-turn window, and the unbounded read is that filter at full breadth, the
user-visible mirror of the cs-3 full-history relation (the persona-visible
cs-3 face itself keeps teaching letters out of the assistant side: that is
the role's reading, not the archive's). ``GET
/api/target_footprint?id=<target_id>`` is the cross-letter footprint (the
9.12-23④ preview item, closed here): one expression's ACTIVE learning
evidence distributed over the turns that produced it — per turn the claim
count and the outcomes as the evaluator wrote them; a target with no
evidence answers ``{"found": false}``, a 200 fact, never a 404.
"""

from __future__ import annotations

import dataclasses
import json
import math
import queue
import re
import socket
import sqlite3
import sys
import threading
import time
import uuid
from datetime import UTC, datetime
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Sequence, TextIO
from urllib.parse import parse_qs, urlsplit

from elc import lexicon as _lexicon
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
from elc.persona.official import OFFICIAL_CHARACTER_PACKAGES
from elc.persona.penpal import (
    PENPAL_CHARACTER_PACKAGE,
    PENPAL_CHARACTER_PACKAGE_ID,
    PENPAL_PERSONA_ID,
)
from elc.persona.provider import PersonaProvider
from elc.persona.types import (
    RESPONSE_LANGUAGE_WORDS,
    CompiledPrompt,
    ProviderOutput,
)
from elc.planner.trace_document import decode_factor_trace
from elc.platform.db.app_settings import (
    APP_SETTING_PROVIDER_ACTIVE_PROFILE_KEY,
    APP_SETTING_PROVIDER_API_KEY_KEY,
    APP_SETTING_PROVIDER_BASE_URL_KEY,
    APP_SETTING_PROVIDER_MODEL_KEY,
    APP_SETTING_PROVIDER_PROFILE_PREFIX,
    APP_SETTING_REPLY_LANGUAGE_KEY,
    APP_SETTING_ROLLOUT_STAGE_KEY,
    APP_SETTING_UI_LANGUAGE_KEY,
)
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
    Ok,
    PersonaId,
    PolicyVersion,
    TargetId,
)
from elc.runtime.controller import TeachingReplyRequest
from elc.runtime.types import InputEnvelope
from elc.scheduler.types import ScheduleItem
from elc.teaching.envelope import (
    AttemptPayload,
    TeachingControlIntent,
    TeachingResponseEnvelope,
)
from elc.teaching.request import TeachingRequest
from elc.teaching.rollout import OBSERVATION_SPECS, ROLLOUT_STAGES, RolloutStage
from elc.teaching.types import MomentState
from elc.user_config.types import (
    DisclosureLevel,
    DisclosurePolicy,
    DisclosureRule,
    LearningGoal,
    LearningGoalPortfolio,
    SessionFocus,
    TeachingFrequency,
    TeachingPolicyProfile,
)
from elc.world.engine.orchestrate import (
    TRIGGER_LETTER,
    run_step,
)
from elc.world.engine.types import EngineConfig
from elc.world.package import (
    BUILTIN_WORLDS_DIR,
    WorldPackage,
    _actor_id_for,
    load_world_package,
    world_date_of,
)
from elc.world.store import WorldRevealItem

__all__ = [
    "DEFAULT_WEB_CONVERSATION_ID",
    "WebOpenError",
    "main",
    "port_is_serving",
    "run_web",
]


#: The world inbox's no-binding answer (W-1-3): one sentence, shared by
#: the two routes that need it (an inbox that does not exist is not an
#: empty one — the world is bound per conversation, never global).
_WORLD_NO_BINDING = (
    "这个对话没有绑定任何世界——收件箱不存在（世界是对话绑定的，不是全局的）。"
)

#: The overview's quiet-day sentences (wf-0): one human line per interface
#: language — the honest fact that today carries no revealed note. It says
#: nothing about what still waits unread: reading is not opening, and the
#: ``PENDING`` slice stays out of every read face's answer.
_WORLD_QUIET_DAY: dict[str, str] = {
    "zh": "今天风平浪静——还没有新的动静。",
    "en": "A quiet day — nothing new has come ashore.",
}

#: The virtual world calendar's presentation words (A2, DEC-…88/…90).
#: ``_MONTH_ABBR`` is written out (never ``%b``) so the English date is
#: the same in every locale; the zh side spells 月/日 itself. No year —
#: the story's year sense is the setting's business, not the chrome's.
_MONTH_ABBR: tuple[str, ...] = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)

#: The virtual-calendar date shape (``YYYY-MM-DD``, :meth:`re.fullmatch`):
#: the honest discriminator between a story-dated event (the A2 stamp —
#: the day the presentation faces render) and a legacy row whose
#: ``occurred_at`` carries a real wall-clock moment (those render **no**
#: date at all — an honest old row is never dressed up as a story day).
_ISO_DAY_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _localize_story_date(
    day: str, ui_language: str, world_name: str | None = None
) -> str:
    """One story day, in the interface language: zh ``9月21日`` / en
    ``Sep 21``, plus `` · <world name>`` when the caller wants the full
    story-block headline. Deterministic in the locale (the month table
    above), never a wall-clock read."""

    year, month, day_of_month = day.split("-")
    if ui_language == "zh":
        text = f"{int(month)}月{int(day_of_month)}日"
    else:
        text = f"{_MONTH_ABBR[int(month) - 1]} {int(day_of_month)}"
    if world_name:
        text += f" · {world_name}"
    return text


class WebOpenError(RuntimeError):
    """The conversation the page serves could not be opened (run_web raises
    before binding; the CLI branch answers it with chat's open-failure
    shape — one human sentence and exit 1, never a 500-per-request loop)."""

#: The default conversation the web face opens (idempotent; distinct from the
#: CLI's so the two surfaces never interleave one transcript by accident).
DEFAULT_WEB_CONVERSATION_ID = "web-default"

#: How many canonical turns ``/api/history`` serves by default (the page's
#: load-time recovery window). 主线-2 keeps this the no-parameter answer —
#: the explicit ``?full=1`` / ``?limit=N`` parameters serve more, and the
#: default window's semantics are pinned unchanged.
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

#: The favicon (v3-d 清扫, the v31R 登记「favicon 既有」): one inline SVG —
#: the paper tone with an ink-line envelope, the same 纸墨语汇 as the page's
#: brand mark (two geometries, one design language; the page's copy lives
#: in index.html's template because HTML parses inline SVG without the
#: namespace string, which this file — read as a standalone document —
#: must declare). Served same-origin at ``/favicon.ico`` so the browser's
#: automatic discovery request stops 404-ing; the webui source stays free
#: of every URI scheme (the zero-external law's pins are untouched: no
#: ``http(s)://``, no ``data:`` — the namespace string lives here, on the
#: Python side of the shell).
_FAVICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
    '<rect width="32" height="32" fill="#efe9dc"/>'
    '<rect x="5.5" y="9.5" width="21" height="13" fill="#efe9dc"'
    ' stroke="#191b1e" stroke-width="1.5"/>'
    '<path d="M6 10l10 7 10-7" fill="none" stroke="#191b1e"'
    ' stroke-width="1.5"/>'
    "</svg>"
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


def _schedule_item_face(item: ScheduleItem) -> dict[str, Any]:
    """One §5.2 row for the schedule zone — the row's own columns verbatim.

    The classified view's items pass through as the Scheduler wrote them
    (window pair, spacing stage, urgency); the one derived field is the
    display name out of the id (:func:`_target_display_name`'s reading,
    the same one the teach rows use).
    """

    return {
        "target_type": item.target_type,
        "target_id": str(item.target_id),
        "name": _target_display_name(str(item.target_id)),
        "review_state": item.review_state.value,
        "review_urgency": item.review_urgency,
        "next_review_window_start": item.next_review_window_start,
        "next_review_window_end": item.next_review_window_end,
        "spacing_stage": (
            None if item.spacing_stage is None else item.spacing_stage.value
        ),
        "updated_at": item.updated_at,
    }


def _history_request(
    params: dict[str, list[str]],
) -> tuple[str | None, bool, int | None]:
    """The ``/api/history`` query grammar, fail-closed.

    No query is the unchanged default window; ``?full=1`` is the whole
    user-visible transcript; ``?limit=<n>`` is the ``n`` most recent
    turns (a whole number from 1 up — a zero or negative bound is not a
    breadth, it is a typo, and it gets the 400 人话). The two parameters
    are mutually exclusive (one read, one breadth) and any other key
    names itself in its own refusal — never a silent drop.
    """

    full_values = params.get("full")
    limit_values = params.get("limit")
    unknown = sorted(set(params) - {"full", "limit"})
    if unknown:
        return (
            f"unknown parameter {unknown[0]!r} — /api/history takes"
            " ?full=1 or ?limit=<n>",
            False,
            None,
        )
    if full_values is not None and limit_values is not None:
        return (
            "use either ?full=1 or ?limit=<n>, not both",
            False,
            None,
        )
    if full_values is not None:
        if full_values != ["1"]:
            return ("?full takes the one value 1", False, None)
        return (None, True, None)
    if limit_values is not None:
        if len(limit_values) != 1:
            return ("?limit takes one whole number", False, None)
        try:
            limit = int(limit_values[0])
        except ValueError:
            return ("?limit takes a whole number of turns", False, None)
        if limit < 1:
            return (
                "?limit takes a whole number of turns from 1 up",
                False,
                None,
            )
        return (None, False, limit)
    return (None, False, None)


# ---------------------------------------------------------------------------
# fr-A token metering — the usage read faces (read-only SQL on the work
# queue, the diagnostics construction: plain SELECTs, never a write)
# ---------------------------------------------------------------------------

#: The usage sums over one provider-attempt group: SQL's SUM ignores
#: NULLs — an endpoint that reports no usage contributes nothing, so the
#: sums are the *measured* consumption only (never a fabricated 0), and
#: the measured/total call pair says how much of the traffic was metered
#: at all. Every provider attempt of every generation action joins in —
#: a retry's consumption is real consumption.
_USAGE_SUMS = (
    "SUM(p.prompt_tokens), SUM(p.completion_tokens), SUM(p.total_tokens),"
    " COALESCE(SUM(CASE WHEN p.prompt_tokens IS NOT NULL"
    " OR p.completion_tokens IS NOT NULL"
    " OR p.total_tokens IS NOT NULL THEN 1 ELSE 0 END), 0),"
    " COUNT(*)"
)
_USAGE_JOINS = (
    " FROM provider_attempt p"
    " JOIN generation_action_intent g ON g.action_id = p.action_id"
)


def _usage_face(sums: tuple[Any, ...]) -> dict[str, Any] | None:
    """One usage sums tuple as the per-turn payload face — ``None`` when
    nothing was metered (the turn's attempts reported no usage at all)."""

    if not sums[3]:
        return None
    return {
        "prompt_tokens": sums[0],
        "completion_tokens": sums[1],
        "total_tokens": sums[2],
    }


def _usage_totals(db: sqlite3.Connection, conversation_id: str) -> dict[str, Any]:
    """The conversation-wide cumulative usage (fr-A): every attempt of
    every action bound to this conversation's turns, window-independent —
    the session's whole measured consumption, so a widened or narrowed
    history read never changes it."""

    row = db.execute(
        "SELECT " + _USAGE_SUMS + _USAGE_JOINS
        + " JOIN user_turn u ON u.turn_id = g.turn_id"
          " WHERE u.conversation_id = ?",
        (conversation_id,),
    ).fetchone()
    return {
        "prompt_tokens": row[0],
        "completion_tokens": row[1],
        "total_tokens": row[2],
        "measured_calls": int(row[3]),
        "total_calls": int(row[4]),
    }


def _usage_by_turn(
    db: sqlite3.Connection, turn_ids: list[str]
) -> dict[str, dict[str, Any] | None]:
    """The window's per-turn usage: one sums row per turn, ``None`` for a
    turn nothing was metered on. The placeholder list is the only
    generated text (the ``count_delivered_teaching_turns`` precedent)."""

    if not turn_ids:
        return {}
    placeholders = ", ".join("?" for _ in turn_ids)
    rows = db.execute(
        "SELECT g.turn_id, " + _USAGE_SUMS + _USAGE_JOINS
        + " WHERE g.turn_id IN (" + placeholders + ")"
          " GROUP BY g.turn_id",
        tuple(turn_ids),
    ).fetchall()
    return {str(row[0]): _usage_face(row[1:5]) for row in rows}


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


def _partner_card_face(
    record: CharacterCardRecord | None = None,
) -> dict[str, Any]:
    """The character card's narrative face, shaped for the page.

    The single-source rule (cs-1, pinned) makes this a derivation, never a
    second spelling. Queue ④: when the served conversation names a
    character (any roster card — the official family seeded beside the
    penpal, or a user's own), the face reads that **table row** — the
    same five keys :func:`_character_card_face` serves, so the dossier
    follows the switch and a reworded card reads reworded. When the
    conversation names no card at all (the shipped default before any
    switch in the cs-1 world; the tests' own conversations), the face
    falls back to :data:`PENPAL_CHARACTER_PACKAGE` — the prompt
    compiler's own fallback rule, restated for the dossier. The three
    prose fields pass through whole (the page renders them as the
    dossier's paragraphs, it does not re-shape the words). Nothing here
    hardcodes a value of the character: a changed card changes this face.
    """

    if record is None:
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
    return _character_card_face(record)


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
    """A query or a lemma as lowercased, edge-stripped word tokens.

    The curly apostrophe (U+2019 — the form model output actually writes)
    normalizes to the straight one before anything else, so ``it's`` in a
    letter and ``it's`` in the lexicon data meet as the same token (the
    v3-3 组合第 3 件)."""

    tokens: list[str] = []
    for raw in str(text).split():
        token = raw.strip(_WORD_EDGE_CHARS)
        token = token.replace("’", "'").casefold()
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
    (:data:`_WORD_PASSTHROUGH_ROLES`), examples are the entity's own
    ``content_example`` rows, primary-target first — they carry no
    ``sense_id``, so the same ≤2 list rides every sense of the entity
    (today one sense per entity) — and the scenario-variant rows
    (``usage`` at ordinal ≥ 2, queue-3) ride ``usage_variants`` with
    their aligned ``content_resource_label`` context/genre words.
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
        # The second tier (v3-3 组合第 2 件): a single-token query that the
        # corpus cannot answer falls to the offline mini-dictionary — a
        # *dictionary* card (head word + pos + gloss), never a teaching
        # card. Multi-token queries stay corpus-only (the "make senses"
        # boundary: the dictionary never participates in phrase matching),
        # and a dictionary miss is the same honest {"found": false}.
        if len(q_tokens) == 1:
            entry = _lexicon.lookup(q_tokens[0])
            if entry is not None:
                return {
                    "found": True,
                    "source": "lexicon",
                    "lemma": entry.head,
                    "pos": entry.pos,
                    "gloss": entry.gloss,
                    "matched": entry.matched,
                }
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
    # The scenario-variant face (queue-3): the evidence texts block may carry
    # extra ``usage`` rows at ordinal >= 2 — the same expression re-seated in
    # a distinct real context, each aligned with the resource_labels row of
    # the same ordinal. The read joins that aligned label row for the card's
    # small context tag; a target with no variants (the common case) reads
    # an empty list and the page renders nothing there.
    usage_variants = [
        {
            "text": str(row[0]),
            "context": row[1] if row[1] is not None else None,
            "genre": row[2] if row[2] is not None else None,
        }
        for row in conn.execute(
            "SELECT t.text, l.context, l.genre FROM content_text t"
            " LEFT JOIN content_resource_label l"
            " ON l.entity_id = t.entity_id AND l.ordinal = t.ordinal"
            " WHERE t.entity_id = ? AND t.role = 'usage' AND t.ordinal >= 2"
            " ORDER BY t.ordinal",
            (entity_id,),
        )
    ]
    return {
        "found": True,
        "source": "corpus",
        "lemma": lemma,
        "pos": pos,
        "forms": forms,
        "senses": senses,
        "usage_variants": usage_variants,
        "entity_id": entity_id,
    }


#: The click-window widths, longest first — the same 3/2/1 the page's
#: ``wordWindows`` walks (components.js), so the hit bitmap and a real
#: click agree by construction (both sides feed the same ``_word_tokens``
#: + ``_contains_run`` + dictionary covers check).
_WINDOW_SIZES = (3, 2, 1)


def _letter_paragraphs(text: str) -> list[str]:
    """A letter as paragraphs — the page's own split (``letterParagraphs``:
    runs of newlines, each paragraph trimmed, empties dropped), mirrored
    here so the bitmap's paragraph rows line up with the rendered ones."""

    return [p.strip() for p in re.split(r"\n+", str(text)) if p.strip()]


def _word_hit_row(words: list[str], lemma_runs: tuple[list[str], ...]) -> list[int]:
    """One paragraph's hit bitmap: for each whitespace word, whether one
    of its 1–3 word windows would answer a real click (corpus containment
    on the same normalization, or — single-token windows only — the
    dictionary). The affordance face of §3(b): a 0 word is rendered
    without the clickable style, so "miss silence" becomes "no
    affordance" instead of a dead tap."""

    row: list[int] = []
    for index in range(len(words)):
        hit = False
        for size in _WINDOW_SIZES:
            start = max(0, index - size + 1)
            while not hit and start <= index and start + size <= len(words):
                query = _word_tokens(" ".join(words[start : start + size]))
                if query and (
                    any(_contains_run(query, run) for run in lemma_runs)
                    or (
                        len(query) == 1
                        and _lexicon.covers(query[0])
                    )
                ):
                    hit = True
                start += 1
        row.append(1 if hit else 0)
    return row


def _letter_hit_rows(
    text: str, lemma_runs: tuple[list[str], ...] | None
) -> list[list[int]] | None:
    """A whole letter's hit bitmap (one row per paragraph), or ``None``
    when this host has no word list (the honest shape: without the
    content leg every word keeps today's full affordance)."""

    if lemma_runs is None:
        return None
    return [
        _word_hit_row(paragraph.split(), lemma_runs)
        for paragraph in _letter_paragraphs(text)
    ]


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


#: 主线-1（DEC-OPI-76a0a10a-….30）: the eight §5.1 columns the settings
#: write face accepts — the knob whitelist, in §5.1's column order
#: (``teaching_frequency`` first, then the seven unpinned columns). Every
#: other key in a write body is refused, never dropped.
_SETTINGS_KNOBS: tuple[str, ...] = (
    "teaching_frequency",
    "interruption_budget",
    "curriculum_initiative",
    "correction_strictness",
    "hint_policy",
    "assessment_visibility",
    "practice_density",
    "persona_freedom",
)

#: The §5.1 policy columns that are not knobs — the write body's refused
#: system columns. ``version`` is carried under both of its declared
#: spellings (the canonical word and the qualified alias the §5.1
#: implementation documents), so a body that names either gets the same
#: honest refusal instead of slipping past a spelling check. ``mode`` is
#: not among them since the veto-response cut: the §12 stage moved to its
#: own write (``/api/settings/mode``), and a body that still names
#: ``mode`` here gets the unknown-key sentence — the old "由启动命令给定"
#: refusal is retired with the read-only reading it defended.
_SETTINGS_SYSTEM_COLUMNS: tuple[str, ...] = (
    "teaching_policy_profile_id",
    "version",
    "policy_version",
    "effective_from",
    "updated_at",
)

#: The §12 stage words — the mode write's whitelist, read from the enum
#: (the same spelling discipline as the frequency words: case-sensitive,
#: the words are the document's). Importing keeps one vocabulary: a stage
#: added to :class:`~elc.teaching.rollout.RolloutStage` rides the whitelist
#: without a second literal.
_MODE_WORDS: tuple[str, ...] = tuple(stage.value for stage in ROLLOUT_STAGES)

#: The mode write's 400 sentence — one grammar line naming the four words.
_MODE_GRAMMAR = f'need a JSON body {{"stage": {" | ".join(_MODE_WORDS)}}}'


#: The knob write's own frequency sentence (the same four words the goal
#: screen's picker takes — one vocabulary, two doors).
_SETTINGS_FREQUENCY_GRAMMAR = (
    f'"teaching_frequency" needs one of {" | ".join(_FREQUENCY_WORDS)}'
)


def _mode_request_word(payload: Any) -> str | None:
    """The mode write's body, parsed and fail-closed (the W1 law).

    Returns the stage word, or ``None`` when the body is not the one-key
    shape (``{"stage": word}``) or the word is outside the four §12 words
    (case-sensitive — the whitelist is the enum's own values). No default:
    an absent or malformed body is a refusal, never a guessed tier.
    """

    if not isinstance(payload, dict):
        return None
    if set(payload) != {"stage"}:
        return None
    word = payload["stage"]
    if not isinstance(word, str) or word not in _MODE_WORDS:
        return None
    return word


#: The W-L language settings' whitelists. The reply language's words are
#: the compiler's own vocabulary (``elc.persona.types``), imported — one
#: vocabulary, two doors, so a word the page can write is always a word
#: the request type accepts. The interface language is the page's own
#: presentation word, declared here (full-page i18n is registered out of
#: scope; this word moves the world inbox's bilingual face).
_UI_LANGUAGE_WORDS: tuple[str, ...] = ("zh", "en")

#: The two writes' 400 sentences — one grammar line each, naming the words.
_UI_LANGUAGE_GRAMMAR = (
    'need a JSON body {"ui_language": ' + " | ".join(_UI_LANGUAGE_WORDS) + "}"
)
_REPLY_LANGUAGE_GRAMMAR = (
    'need a JSON body {"reply_language": '
    + " | ".join(RESPONSE_LANGUAGE_WORDS)
    + "}"
)


def _language_request_word(
    payload: Any, key: str, words: tuple[str, ...]
) -> str | None:
    """A language write's body, parsed and fail-closed (the mode write's
    law restated, keyed): the one-key shape ``{key: word}`` with the word
    inside the whitelist (case-sensitive), or ``None`` — an absent or
    malformed body is a refusal, never a guessed language."""

    if not isinstance(payload, dict):
        return None
    if set(payload) != {key}:
        return None
    word = payload[key]
    if not isinstance(word, str) or word not in words:
        return None
    return word


def _provider_request_pair(
    payload: Any,
) -> tuple[str | None, str | None, str | None, str | None]:
    """The provider write's body, parsed and fail-closed.

    Returns ``(error, base_url, model, api_key)``: ``error`` is a human
    refusal sentence or ``None``; on success exactly the fields the body
    carried (``{"base_url": str}``, ``{"model": str}`` and/or
    ``{"api_key": str}`` — at least one; the face fills the others from the
    live pair). A base_url must parse with an ``http``/``https`` scheme and
    a netloc; a model must be a non-empty string (length ≤ 200); an api_key
    must be a non-empty string (length ≤ 400). No defaulting, no guessing:
    a malformed body is a refusal.
    """

    if not isinstance(payload, dict) or not payload:
        return ("请求体须是 JSON，至少带 base_url、model 或 api_key 之一。",
                None, None, None)
    unknown = sorted(set(payload) - {"base_url", "model", "api_key"})
    if unknown:
        return (
            "只认 base_url、model 与 api_key 三个键——多出来的键是 "
            + "、".join(unknown) + "。",
            None,
            None,
            None,
        )
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    if "base_url" in payload:
        raw = payload["base_url"]
        if not isinstance(raw, str) or not raw.strip():
            return ("base_url 须是非空字符串。", None, None, None)
        parts = urlsplit(raw.strip())
        if parts.scheme not in ("http", "https") or not parts.netloc:
            return (
                "base_url 须是完整的 http(s) 端点地址（含主机名），"
                "例如 https://api.example.com/v1。",
                None,
                None,
                None,
            )
        base_url = raw.strip()
    if "model" in payload:
        raw = payload["model"]
        if not isinstance(raw, str) or not raw.strip() or len(raw) > 200:
            return ("model 须是非空字符串（≤200 字符）。", None, None, None)
        model = raw.strip()
    if "api_key" in payload:
        raw = payload["api_key"]
        if not isinstance(raw, str) or not raw.strip() or len(raw) > 400:
            return ("api_key 须是非空字符串（≤400 字符）。", None, None, None)
        api_key = raw.strip()
    return (None, base_url, model, api_key)


_PROFILE_ID_PATTERN = r"[A-Za-z0-9_-]{1,40}"


def _profile_id_request(payload: Any) -> str | None:
    """The activate/delete bodies: exactly ``{"id": str}`` inside the id
    pattern (fail-closed — no default, no guessing)."""

    if not isinstance(payload, dict) or set(payload) != {"id"}:
        return None
    pid = payload["id"]
    if not isinstance(pid, str) or not re.fullmatch(_PROFILE_ID_PATTERN, pid):
        return None
    return pid


def _provider_profile_request(
    payload: Any,
) -> tuple[
    str | None, str | None, str, str, str, str | None
]:
    """The profile-save body, parsed and fail-closed:
    ``(error, id, name, base_url, model, api_key)`` — ``name`` is required
    (≤60 chars), ``base_url`` / ``model`` required with the main face's
    grammar, ``id`` and ``api_key`` optional.
    """

    if not isinstance(payload, dict):
        return ("请求体须是 JSON 对象。", None, "", "", "", None)
    allowed = {"id", "name", "base_url", "model", "api_key"}
    unknown = sorted(set(payload) - allowed)
    if unknown:
        return (
            "只认 id、name、base_url、model 与 api_key——多出来的键是 "
            + "、".join(unknown) + "。",
            None,
            "",
            "",
            "",
            None,
        )
    for required in ("name", "base_url", "model"):
        if required not in payload:
            return (f"缺 {required}——配置档要名字、端点和模型名。",
                    None, "", "", "", None)
    name = payload["name"]
    if not isinstance(name, str) or not name.strip() or len(name) > 60:
        return ("name 须是非空字符串（≤60 字符）。", None, "", "", "", None)
    base_url: str | None
    raw_base = payload["base_url"]
    if not isinstance(raw_base, str) or not raw_base.strip():
        return ("base_url 须是非空字符串。", None, "", "", "", None)
    parts = urlsplit(raw_base.strip())
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return (
            "base_url 须是完整的 http(s) 端点地址（含主机名）。",
            None,
            "",
            "",
            "",
            None,
        )
    base_url = raw_base.strip()
    model = payload["model"]
    if not isinstance(model, str) or not model.strip() or len(model) > 200:
        return ("model 须是非空字符串（≤200 字符）。", None, "", "", "", None)
    profile_id: str | None = None
    if "id" in payload:
        raw_id = payload["id"]
        if (
            not isinstance(raw_id, str)
            or not re.fullmatch(_PROFILE_ID_PATTERN, raw_id)
        ):
            return ("id 须是字母数字、短横或下划线（≤40 字符）。",
                    None, "", "", "", None)
        profile_id = raw_id
    api_key: str | None = None
    if "api_key" in payload:
        raw_key = payload["api_key"]
        if (
            not isinstance(raw_key, str)
            or not raw_key.strip()
            or len(raw_key) > 400
        ):
            return ("api_key 须是非空字符串（≤400 字符）。",
                    None, "", "", "", None)
        api_key = raw_key.strip()
    return (None, profile_id, name.strip(), base_url, model.strip(), api_key)


def _settings_system_column_refusal(key: str) -> str:
    """The 400 sentence for a refused system column — the column names
    itself and the write face names its own whitelist."""

    return f"「{key}」是系统列，不由页面写（可写面只有八个旋钮）。"


def _settings_knob_request(
    payload: Any,
) -> tuple[str | None, dict[str, Any] | None]:
    """The settings write body, parsed and fail-closed (the W1 law).

    Returns ``(error, knobs)``: a non-empty ``error`` is the 400 人话
    sentence; a ``None`` error means the eight knobs are in grammar. The
    body is the **full new knob set** (all eight keys — the W1 full-
    combination shape, so the version discipline's replay comparison is
    well-defined); a key outside the whitelist is refused with its own
    sentence — a system column names itself, an unknown key names itself
    (``mode`` included since the veto-response cut: the §12 tier's write
    is ``/api/settings/mode``, not a knob). ``teaching_frequency`` must be
    one of the enum's own four words (case-sensitive); the seven unpinned
    knobs take a non-empty string (carried verbatim — the store is a
    shelf, the card store's rule) or ``null`` (= 未配置, the column's own
    honesty). An out-of-vocabulary word is refused, never silently
    dropped.
    """

    if not isinstance(payload, dict):
        return (
            "need a JSON body with the eight knobs: "
            + ", ".join(_SETTINGS_KNOBS),
            None,
        )
    for key in payload:
        if key in _SETTINGS_KNOBS:
            continue
        if key in _SETTINGS_SYSTEM_COLUMNS:
            return (_settings_system_column_refusal(key), None)
        return (f"不认识的键：{key}（可写面只有八个旋钮）。", None)
    for key in _SETTINGS_KNOBS:
        if key not in payload:
            return (
                f'"{key}" is missing: the body is the full new knob set'
                f" ({', '.join(_SETTINGS_KNOBS)})",
                None,
            )
    frequency = payload["teaching_frequency"]
    if not isinstance(frequency, str) or frequency not in _FREQUENCY_WORDS:
        return (_SETTINGS_FREQUENCY_GRAMMAR, None)
    knobs: dict[str, Any] = {"teaching_frequency": frequency}
    for key in _SETTINGS_KNOBS[1:]:
        value = payload[key]
        if value is None:
            knobs[key] = None
        elif isinstance(value, str) and value.strip():
            knobs[key] = value
        else:
            return (f'"{key}" needs a non-empty string or null', None)
    return (None, knobs)


def _disclosure_request_rules(
    payload: Any,
) -> tuple[str | None, list[DisclosureRule] | None]:
    """The disclosure write body, parsed and fail-closed (fr-A; the knob
    write's W1 law, restated).

    Returns ``(error, rules)``: a non-empty ``error`` is the 400 人话
    sentence; a ``None`` error means the rule set is in grammar. The body
    is the **full new rule set** (``{"rules": [...]}`` — the version
    discipline's replay comparison is well-defined): each rule carries
    exactly ``persona_id`` (a non-empty string, or ``null`` for the default
    rule) and ``disclosure_level`` (one of the enum's own three words,
    case-sensitive). A duplicate rule for one persona — the default rule
    included — is refused with its own sentence: the disclosure decision
    takes the first match, so a second row would be silently dead
    configuration. An out-of-vocabulary level is refused, never silently
    dropped; an empty rule set is legal (the fail-closed default: nothing
    is disclosed).
    """

    if not isinstance(payload, dict):
        return ('need a JSON body with "rules": the full new rule set', None)
    unknown = sorted(set(payload) - {"rules"})
    if unknown:
        return (f"不认识的键：{unknown[0]}（可写面只有 rules）。", None)
    rules = payload.get("rules")
    if not isinstance(rules, list):
        return ('"rules" must be a list: the full new rule set', None)
    levels = {level.value for level in DisclosureLevel}
    parsed: list[DisclosureRule] = []
    seen: set[str | None] = set()
    for index, item in enumerate(rules):
        if not isinstance(item, dict):
            return (f"rules[{index}] 须是对象（persona_id + disclosure_level）。",
                    None)
        extra = sorted(set(item) - {"persona_id", "disclosure_level"})
        if extra:
            return (f"rules[{index}] 有不认识的键：{extra[0]}。", None)
        persona = item.get("persona_id")
        if persona is not None and (
            not isinstance(persona, str) or not persona.strip()
        ):
            return (f"rules[{index}].persona_id 须是非空字符串或 null（默认规则）。",
                    None)
        level_word = item.get("disclosure_level")
        if not isinstance(level_word, str) or level_word not in levels:
            return (
                f"rules[{index}].disclosure_level 须是三词之一："
                + ", ".join(sorted(levels)),
                None,
            )
        key = None if persona is None else persona
        if key in seen:
            who = "默认规则" if persona is None else f"角色 {persona}"
            return (
                f"{who}出现了两条——一个对象只能有一条披露规则"
                "（重复行是死配置，拒收）。",
                None,
            )
        seen.add(key)
        parsed.append(
            DisclosureRule(
                persona_id=None if persona is None else PersonaId(persona),
                disclosure_level=DisclosureLevel(level_word),
            )
        )
    return (None, parsed)


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


def _settings_policy_face(policy: TeachingPolicyProfile) -> dict[str, Any]:
    """The settings read's policy face — the §5.1 TeachingPolicyProfile's
    thirteen columns, verbatim.

    ``version`` rides under its declared alias ``policy_version`` (the
    qualified spelling ``elc.user_config.types`` documents — the canonical
    column is ``version``, and no sentence here claims a word-for-word
    equality). ``effective_from`` carries the F-4 ``""`` sentinel as the
    value it is, ``updated_at`` is the store's own clock, and the seven
    unpinned knobs pass through raw (``None`` = 未配置). ``mode`` (the
    §5.1 row's own column) rides along verbatim: the knob write face does
    not accept it (never has), and this read is where the page sees it as
    the row holds it.
    """

    return {
        "teaching_policy_profile_id": str(policy.teaching_policy_profile_id),
        "policy_version": str(policy.policy_version),
        "mode": policy.mode,
        "teaching_frequency": str(policy.teaching_frequency.value),
        "interruption_budget": policy.interruption_budget,
        "curriculum_initiative": policy.curriculum_initiative,
        "correction_strictness": policy.correction_strictness,
        "hint_policy": policy.hint_policy,
        "assessment_visibility": policy.assessment_visibility,
        "practice_density": policy.practice_density,
        "persona_freedom": policy.persona_freedom,
        "effective_from": policy.effective_from,
        "updated_at": policy.updated_at,
    }


def _settings_disclosure_face(policy: DisclosurePolicy) -> dict[str, Any]:
    """The settings read's disclosure face — the §5.1 DisclosurePolicy's
    four columns, verbatim.

    The rules ride as the row holds them (``persona_id: null`` = the
    default rule — the one that can never authorize high-sensitivity
    disclosure), so the page shows the authorization about content exactly
    as it stands. Display only: this face writes nothing, and the section's
    copy says the rules are edited through the profile, not here.
    """

    return {
        "disclosure_policy_id": str(policy.disclosure_policy_id),
        "revision": str(policy.revision),
        "rules": [
            {
                "persona_id": (
                    None if rule.persona_id is None
                    else str(rule.persona_id)
                ),
                "disclosure_level": str(rule.disclosure_level.value),
            }
            for rule in policy.rules
        ],
        "updated_at": policy.updated_at,
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


# ---------------------------------------------------------------------------
# A1: the streamed turn's bridge (the live generation half lives here; the
# SSE writing lives on the handler).
# ---------------------------------------------------------------------------


class _StreamingProviderProxy:
    """One streamed turn's provider: ``call_streaming`` with its emit
    wired straight to the turn's queue (DEC-…77: the live reading).

    The live provider's optional streaming face runs the real request; every
    increment goes to the page **as it arrives** — the guard this owes is
    the adapter's own key-echo check, which runs on the accumulated buffer
    *before* every emit, so nothing reaches the queue un-checked. The
    buffered contract still holds on the return value, so the generation
    pipeline keeps its exact retry and validation semantics; a turn whose
    validation fails answers its failure shape as the final frame, and the
    page's existing reconcile posture (the human line + a history pull)
    owns what was already shown. Installed and removed inside one
    work-queue job (:meth:`_WebFace.turn_stream`), so no other face — the
    settings provider face included — ever observes it.
    """

    def __init__(self, real: PersonaProvider, bridge: "_TurnStreamBridge"):
        self._real = real
        self._bridge = bridge

    def call(self, prompt: CompiledPrompt) -> ProviderOutput:
        return self._real.call_streaming(  # type: ignore[attr-defined]
            prompt, self._bridge.push
        )


class _TurnStreamBridge:
    """One streamed turn's live delta channel (A1, DEC-…77).

    The queue is the page's delta stream: the provider proxy pushes each
    SSE increment as it arrives, and the request's handler thread drains
    the queue into SSE delta frames while the host thread is still inside
    the turn. The durable delivery is deliberately untouched — the seam
    keeps its constructor default, so the §22 rows and the transcript of a
    streamed turn are exactly a blocking turn's.
    """

    def __init__(self, events: "queue.Queue[str]") -> None:
        self._events = events

    def push(self, text: str) -> None:
        """Hand one live increment to the page's delta stream."""

        self._events.put(text)


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
        # The affordance face's one cache (v3-3): the corpus lemmas as
        # token runs, read once from the same artifact the word lookup
        # reads (a face-level memo — the bitmap walks them once per word,
        # and a fresh SELECT per letter would be fifty per history read).
        # A content.db rebuilt underneath a running server is not a
        # supported flow (the face binds at startup); the lookup path
        # still reads per request, so a stale cache can only ever fail
        # toward "no affordance style", never a wrong card.
        self._lemma_runs: tuple[list[str], ...] | None = None
        if self._word_db_path is not None:
            try:
                conn = open_read_only(self._word_db_path)
                try:
                    self._lemma_runs = tuple(
                        _word_tokens(str(lemma))
                        for (lemma,) in conn.execute(
                            "SELECT lemma FROM content_lexical_entry"
                        )
                    )
                finally:
                    conn.close()
            except sqlite3.Error:
                self._lemma_runs = None
        # MC-0: the character card store (the assembly always builds one;
        # getattr with a default for the same test-double reason as the
        # word path above — a stub host simply has no roster, and the
        # roster faces say so loudly instead of pretending).
        self._cards: SqliteCharacterCardStore | None = getattr(
            host, "character_cards", None
        )
        # W-1-3: the builtin world packages, read once (the word-list
        # cache's posture — the assembly's own open already validated every
        # package, so a re-read failing here is exceptional and degrades
        # toward "no world leg": the inbox answers its honest 404 and the
        # turn wiring skips silently, never a broken page). The packages
        # are what the world steps run with (the pool, the engine config's
        # defaults) and what the run_web binding reads (the cast).
        self._world_packages: dict[str, WorldPackage] = {}
        try:
            for package_path in sorted(BUILTIN_WORLDS_DIR.glob("*.json")):
                loaded_package = load_world_package(package_path)
                if isinstance(loaded_package, Ok):
                    self._world_packages[loaded_package.value.world_id] = (
                        loaded_package.value
                    )
        except OSError:
            self._world_packages = {}

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

    def turn(self, text: str, *, skip_world_step: bool = False) -> dict[str, Any]:
        """One committed turn, as the page renders it.

        A2 (DEC-…82): ``skip_world_step`` is the streamed path's
        suppression parameter — ``turn_stream`` runs the world step
        itself, **before** generation, and passes ``True`` here so the
        world runs exactly once per turn (the reply's payload still
        carries the pre-step's note under ``world_step_note``). The
        default keeps the blocking turn's own wiring: the step runs
        after the commit, exactly as W-1-3 shipped it."""

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
        reply = completion.reply_text
        return {
            "reply": reply,
            "turn_status": completion.turn_status.value,
            "failure_reason": completion.failure_reason,
            "teaching_moments": self._moments_of_turn(str(completion.turn_id)),
            # The affordance bitmaps (v3-3 组合第 4 件): which words of the
            # reply — and of the user's own committed letter — a click can
            # actually answer. ``None`` (no content leg) keeps today's
            # full affordance on every word.
            "word_hits": (
                None if reply is None else _letter_hit_rows(reply, self._lemma_runs)
            ),
            "user_word_hits": _letter_hit_rows(text, self._lemma_runs),
            # fr-A: this turn's measured token usage (all its actions'
            # attempts) — ``None`` when the endpoint reported none.
            "usage": _usage_by_turn(
                self._host.db, [str(completion.turn_id)]
            ).get(str(completion.turn_id)),
            # W-1-3's turn wiring (additive, normally ``None``): the bound
            # world's step ran after the turn committed; a step that
            # refused (or blew up) says so here in one human sentence and
            # nothing else about this reply changes — the world leg is
            # fail-soft by contract (the reply is the page's substance;
            # the world's bookkeeping never blocks it). A2: the streamed
            # turn answers the pre-generation step's note here instead
            # (the shape is the same; the step ran earlier).
            "world_step_note": (
                None
                if skip_world_step
                else self._world_step_after_turn(str(completion.turn_id))
            ),
        }

    def turn_stream(
        self, text: str, events: "queue.Queue[Any]"
    ) -> dict[str, Any]:
        """One committed turn through the streamed bridge (A1, DEC-…77),
        with the world's story told first (A2, DEC-…82).

        The payload contract is :meth:`turn`'s, byte for byte — the final
        SSE event carries exactly what ``/api/turn`` would have answered,
        ``world_step_note`` included. The stream half is a capability
        probe: a provider without the optional ``call_streaming`` face
        (every scripted test double among them) runs the blocking turn
        unchanged — the world steps where it always did, inside the turn
        — and the endpoint answers zero deltas with its one final. A
        provider that has the face gets it wrapped for this one turn with
        its emit wired **straight to the turn's queue** — increments
        reach the page as they are generated (each one key-echo-checked
        by the adapter before it is emitted), the durable delivery keeps
        the constructor-default seam, and the swap is restored in the
        ``finally``, so a failure anywhere leaves the assembly exactly as
        it was (the blocking shape, zero deltas, one final).

        A2's narrative order: **world → deltas → final**. Before the
        first generation token, the face runs the world step once (it is
        the millisecond-scale leg — the model call is the slow one) and
        answers the queue with **one structured ``world`` event** (the
        story block's data: the world's name, its virtual-calendar day
        localized, this run's notes in the interface language) so the
        page can tell the world's side of the day before the reply
        starts to arrive. A step that refuses (or blows up) sends no
        world event at all — the deltas simply start; the note, if any,
        still rides the final's ``world_step_note``. The step runs
        **once**: the turn itself is asked to skip its own post-commit
        wiring (``turn(skip_world_step=True)``) and answers the
        pre-step's note instead — one turn, one world advance, the old
        blocking endpoint's behavior untouched.
        """

        live = self._host.coordinator.persona_provider()
        if not hasattr(live, "call_streaming"):
            return self.turn(text)
        # The world first (it is fast), the reply second. The step's
        # trigger turn id rides as ``None`` on purpose: at this point the
        # turn is not committed, so no turn id exists to name — the run
        # row's ``trigger_turn_id`` stays NULL for the streamed path
        # (the column's own ``when it is known`` reading), while the
        # blocking turn keeps naming its own.
        world = self._world_step_face()
        if world["note"] is None and world["bound"]:
            # The structured frame goes through the same queue the delta
            # chunks use; the endpoint writes a dict as its own SSE event
            # and a str as a delta (the drain's ``isinstance`` split). A
            # conversation outside any world tells no story block.
            events.put(self._world_event_payload(world))
        bridge = _TurnStreamBridge(events)
        coordinator = self._host.coordinator
        coordinator.replace_persona_provider(
            _StreamingProviderProxy(live, bridge)
        )
        try:
            payload = self.turn(text, skip_world_step=True)
            payload["world_step_note"] = world["note"]
            return payload
        finally:
            coordinator.replace_persona_provider(live)

    def _world_step_face(self) -> dict[str, Any]:
        """The world step as an independently callable face (A2,
        DEC-…82): one step, then the reveal, then **this run's** notes
        back — ``{"items": [...], "note": str | None}``.

        ``items`` are the notes the step's own run wrote, revealed on
        presentation (the inbox's atomic flip runs here, so what the
        story block shows is exactly what the world meant to say —
        nothing left pending behind it). The presentation is
        **current-run only** (A2, DEC-…90): the page's world face shows
        the latest run's notes, not the world's whole chronicle — the
        older notes stay durable and out of sight. Every failure mode
        answers the sentence in ``note`` and never an exception out;
        ``bound`` says whether this conversation lives in any world at
        all (the streamed path tells no story block without one) — no
        binding (or a host without the world leg) answers an empty face
        silently, the normal arm for hosts and conversations the world
        leg does not name; a world whose package is unreadable or whose
        step refuses says so."""

        binding = self._world_binding()
        if binding is None:
            return {"items": [], "note": None, "bound": False,
                    "at_checkpoint": False}
        world_id = str(binding["world_id"])
        package = self._world_packages.get(world_id)
        world_store = getattr(self._host, "world_store", None)
        if package is None or world_store is None:
            return {"items": [], "note": None, "bound": True,
                    "at_checkpoint": False}
        try:
            stepped = run_step(
                world_store,
                world_id,
                package.to_event_pool(),
                EngineConfig(),
                TRIGGER_LETTER,
                datetime.now(tz=UTC).isoformat(),
                package=package,
            )
        except Exception as exc:  # fail-soft: the sentence, never the raise
            return {
                "items": [],
                "note": f"世界步进失败（回信不受影响）：{type(exc).__name__}: {exc}",
                "bound": True,
                "at_checkpoint": False,
            }
        if isinstance(stepped, Err):
            return {
                "items": [],
                "note": f"世界步进未推进（回信不受影响）：{stepped.error.message}",
                "bound": True,
                "at_checkpoint": False,
            }
        # 呈现即读即揭示: the reveal runs now (the presentation trigger,
        # spec §4.1), so the story block's notes are already the world's
        # read state — the page's later inbox reread adds nothing new.
        revealed = world_store.reveal_all(
            world_id, datetime.now(tz=UTC).isoformat()
        )
        if isinstance(revealed, Err):
            return {
                "items": [],
                "note": (
                    "世界揭示失败（回信不受影响）："
                    f"{revealed.error.code.value}: {revealed.error.message}"
                ),
                "bound": True,
                "at_checkpoint": False,
            }
        step_event_ids = {
            str(cycle.event_id)
            for cycle in stepped.value.cycles
            if cycle.event_id is not None
        }
        items = [
            item
            for item in revealed.value
            if str(item.source_event_id) in step_event_ids
        ]
        latest_run = world_store.list_runs(world_id)[-1]
        return {
            "items": self._story_notes(world_id, package, tuple(items)),
            "note": None,
            "bound": True,
            # The 「继续」 button rides the story block's tail (DEC-…92):
            # the step's own exit state, read from the run row (the same
            # source the inbox's at_checkpoint answers from).
            "at_checkpoint": latest_run.status.value == "AT_CHECKPOINT",
        }

    def _story_notes(
        self,
        world_id: str,
        package: WorldPackage,
        items: tuple[Any, ...],
    ) -> list[dict[str, Any]]:
        """The story-block shape of reveal items: each note's narration
        in the interface language (the package's Chinese prose, or the
        honest English fallback) and its event's story day. No byline,
        no moment word — the story block is prose, not cards (DEC-…82)."""

        ui_language = self._ui_language()
        notes: list[dict[str, Any]] = []
        for item in items:
            event = self._world_event_row(world_id, str(item.source_event_id))
            narration, fallback = self._note_narration(package, ui_language, event)
            notes.append(
                {
                    "narration": narration,
                    "occurred_at": "" if event is None else str(event[3]),
                    "fallback": fallback,
                }
            )
        return notes

    def _ui_language(self) -> str:
        """The interface language row (W-L's own read): the stored word,
        or ``zh`` when nothing is chosen."""

        return (
            self._host.app_settings.get(APP_SETTING_UI_LANGUAGE_KEY) or "zh"
        )

    def _world_event_row(
        self, world_id: str, event_id: str
    ) -> tuple[Any, ...] | None:
        """One chronicle row (the face's direct-SQL read posture): event
        id, narration, kind, occurred_at — or ``None`` when the row is
        gone (a dangling pointer the narration half answers honestly)."""

        row = self._host.db.execute(
            "SELECT event_id, narration, kind, occurred_at"
            " FROM world_event WHERE world_id = ? AND event_id = ?",
            (world_id, event_id),
        ).fetchone()
        return None if row is None else tuple(row)

    def _note_narration(
        self,
        package: WorldPackage | None,
        ui_language: str,
        event: tuple[Any, ...] | None,
    ) -> tuple[str, bool]:
        """One note's narration in the interface language, and its
        fallback bit (W-L's law, shared by the story block and the
        inbox): ``zh`` renders the package's own Chinese prose for the
        event's kind; when the Chinese side does not exist (a v1-era
        durable event whose kind the v3 package never carried, a package
        that failed to load, an unknown kind) the item falls back to the
        English row and says so with ``fallback: True`` — an honest
        English note, never a fabricated Chinese one."""

        english = "" if event is None else str(event[1])
        kind = "" if event is None else str(event[2])
        if ui_language == "zh":
            zh = (
                package.narration_zh_for(kind)
                if package is not None and kind
                else None
            )
            if zh:
                return zh, False
            return english, True
        return english, False

    def _world_event_payload(self, world: dict[str, Any]) -> dict[str, Any]:
        """The streamed ``world`` frame (A2, DEC-…82/…88/…90): the
        world's name, its virtual-calendar day localized (the story's
        own date — :meth:`elc.world.package.world_date_of`, never a wall
        clock), the interface language the frame was rendered in, and
        this run's notes (possibly none — the page's quiet-day arm)."""

        binding = self._world_binding()
        package = (
            None if binding is None
            else self._world_packages.get(str(binding["world_id"]))
        )
        world_store = getattr(self._host, "world_store", None)
        if binding is None or package is None or world_store is None:
            # Unreachable from the streamed path (the frame is only sent
            # for a bound world with a readable package) — the honest
            # defensive answer is an empty frame, never a guessed story.
            return {
                "type": "world",
                "ui_language": self._ui_language(),
                "world_name": None,
                "date_localized": "",
                "notes": [],
            }
        world_id = str(binding["world_id"])
        ui_language = self._ui_language()
        world_name = package.name
        day = world_date_of(package, world_store, world_id)
        return {
            "type": "world",
            "ui_language": ui_language,
            "world_name": world_name,
            "date_localized": _localize_story_date(day, ui_language, world_name),
            "notes": world["items"],
            "at_checkpoint": world["at_checkpoint"],
        }

    def _world_step_after_turn(self, turn_id: str) -> str | None:
        """The turn wiring's fail-soft half (W-1-3's blocking shape):
        one world step, or one human sentence — now a thin caller of
        :meth:`_world_step_face` (A2 lifted the face out so the streamed
        turn can run it before generation; this arm keeps the blocking
        endpoint's byte-for-byte behavior)."""

        return self._world_step_face()["note"]

    def _world_binding(self) -> dict[str, Any] | None:
        """This conversation's world binding row, as a plain mapping (the
        face's own cross-table read shape — the same direct-SQL posture
        the moments and lock reads use), or ``None`` when the
        conversation is bound to no world (or the world leg is absent
        from this host: a stub store is no store)."""

        world_store = getattr(self._host, "world_store", None)
        if world_store is None:
            return None
        try:
            row = self._host.db.execute(
                "SELECT binding_id, world_id, actor_id"
                " FROM world_conversation WHERE conversation_id = ?",
                (str(self._conversation_id),),
            ).fetchone()
        except sqlite3.Error:
            return None
        if row is None:
            return None
        return {
            "binding_id": str(row[0]),
            "world_id": str(row[1]),
            "actor_id": None if row[2] is None else str(row[2]),
        }

    def world_inbox(self) -> tuple[int, dict[str, Any]]:
        """The world inbox: the bound world's atomic reveal, then the
        whole inbox, then the conversation's recent letters.

        One route, three honest answers. No binding (this conversation
        lives in no world — or the host has no world leg) is a **404**
        naming the fact: an inbox that does not exist is not an empty
        one. A reveal refusal is a **500** (the face never fabricates an
        inbox). The happy path rides the work queue like every host
        touch: :meth:`elc.world.store.SqliteWorldStore.reveal_all` flips
        the world's whole ``PENDING`` slice to ``REVEALED`` at this
        moment (spec §4.1 — revealing is the presentation trigger, the
        moment the user next looks) and reads the world's items back,
        revealed history included; each item joins its chronicle event
        for the prose (the item carries the pointer, never a copy) and
        resolves its signature — the comms actor's card name, or
        ``null`` for the world's own narration (the page renders
        「世界」). ``moment`` is the event's chronicle kind word — the
        durable row's own word; the pool's moment vocabulary lives on
        the run, not on the event. ``letters`` is the bound
        conversation's recent correspondence through the history face's
        own window read (read-only, a small explicit slice). The
        ``at_checkpoint`` bit is the world's latest run's own status —
        the page's 「继续」 button is enabled by the world's state, never
        guessed. A2 (DEC-…92): the payload also carries ``revealed_now``
        — the count of ``PENDING`` notes this very read flipped (counted
        **before** the flip) — the load arm's only render trigger (a
        read that revealed nothing renders no world block at all), plus
        ``world_name`` and ``date_localized`` so the page's inline story
        block consumes this payload in the streamed frame's own shape.
        """

        binding = self._world_binding()
        if binding is None:
            return (404, {"error": _WORLD_NO_BINDING})
        world_id = binding["world_id"]
        world_store = getattr(self._host, "world_store", None)
        if world_store is None:
            return (404, {"error": _WORLD_NO_BINDING})
        revealed_now = self._pending_count(str(world_id))
        revealed = world_store.reveal_all(
            str(world_id), datetime.now(tz=UTC).isoformat()
        )
        if isinstance(revealed, Err):
            raise RuntimeError(
                "the world inbox could not be read:"
                f" {revealed.error.code.value}: {revealed.error.message}"
            )
        return 200, self._world_payload(
            str(world_id), revealed.value, revealed_now=revealed_now
        )

    def _pending_count(self, world_id: str) -> int:
        """The world's unread ``PENDING`` note count, read **before** a
        reveal (the count this read will flip — DEC-…92's load-arm
        trigger). Zero is the normal arm: an inbox read that reveals
        nothing renders nothing."""

        row = self._host.db.execute(
            "SELECT COUNT(*) FROM world_reveal_item"
            " WHERE world_id = ? AND status = 'PENDING'",
            (world_id,),
        ).fetchone()
        return int(row[0]) if row is not None else 0

    def _world_payload(
        self,
        world_id: str,
        items: tuple[Any, ...],
        *,
        revealed_now: int = 0,
    ) -> dict[str, Any]:
        """The inbox payload over one revealed item tuple: the items'
        page shape (each joined to its chronicle event for the prose,
        its signature resolved to a card name or ``None`` for the
        world's own narration), the world's ``at_checkpoint`` bit (the
        latest run's own state), and the bound conversation's recent
        letters (the history face's own read, an explicit small slice —
        reuse, never a second transcript implementation).

        W-L: the payload carries the interface language it rendered in
        (the ``ui_language`` setting's row, default ``zh``), and each
        item's narration follows it (the shared narration half with the
        story block — :meth:`_note_narration`; an event the package
        cannot render in Chinese renders its English row and says so
        with ``fallback: true``).

        A2 (DEC-…90): the inbox is **current-run only** — the latest
        run's notes are the world's present; the whole-chronicle
        grouping (「第 N 封信后的世界」) is retired, and the older notes
        stay durable and out of sight (the world's own log face is a
        later cut's). Each note carries ``story_date`` — the event's
        virtual-calendar day (the ``YYYY-MM-DD`` stamp A2 writes),
        localized for the page; a legacy row whose ``occurred_at``
        carries a real wall-clock moment answers ``None`` and renders
        **no** date at all — an honest old row is never dressed up as a
        story day. The payload's own assembly reads no clock (the
        presentation faces' law, DEC-…88 ④).

        A2 / DEC-…92: ``revealed_now`` answers how many unread notes
        this very read flipped (the load arm's only render trigger);
        ``world_name`` and ``date_localized`` (the current run's own
        story day, localized) ride so the page's inline story block
        consumes this payload in the streamed frame's own shape — one
        renderer, two transports."""

        ui_language = self._ui_language()
        package = self._world_packages.get(world_id)
        by_id: dict[str, tuple[Any, ...]] = {}
        for row in self._host.db.execute(
            "SELECT e.event_id, e.narration, e.kind, e.occurred_at"
            " FROM world_event e WHERE e.world_id = ?",
            (world_id,),
        ).fetchall():
            by_id[str(row[0])] = tuple(row)
        actor_names = self._world_actor_names(world_id)
        latest_run = self._host.db.execute(
            "SELECT run_id FROM world_run WHERE world_id = ?"
            " ORDER BY created_at DESC, run_id DESC LIMIT 1",
            (world_id,),
        ).fetchone()
        current_run = str(latest_run[0]) if latest_run is not None else ""
        notes: list[dict[str, Any]] = []
        for item in items:
            event_id = str(item.source_event_id)
            # Current-run only: the event id derives as
            # ``<run_id>:<cursor>``, so the prefix is the run's own name.
            if current_run and not event_id.startswith(f"{current_run}:"):
                continue
            event = by_id.get(event_id)
            narration, fallback = self._note_narration(
                package, ui_language, event
            )
            occurred_at = "" if event is None else str(event[3])
            story_day = (
                _localize_story_date(occurred_at, ui_language)
                if _ISO_DAY_RE.fullmatch(occurred_at)
                else None
            )
            notes.append(
                {
                    "id": item.item_id,
                    "narration": narration,
                    "actor_name": actor_names.get(item.actor_id),
                    "moment": "" if event is None else str(event[2]),
                    "occurred_at": occurred_at,
                    "status": item.status,
                    "fallback": fallback,
                    "story_date": story_day,
                }
            )
        latest = self._host.db.execute(
            "SELECT status FROM world_run WHERE world_id = ?"
            " ORDER BY created_at DESC, run_id DESC LIMIT 1",
            (world_id,),
        ).fetchone()
        recent = self.history(limit=5)
        # DEC-…92: the current run's own story day (its latest event's
        # stamp), localized — the inline story block's date line when
        # this payload rides the load arm or the 「继续」 answer.
        story_day = ""
        for note in reversed(notes):
            if note["story_date"] is not None:
                story_day = str(note["story_date"])
                break
        return {
            "world_id": world_id,
            "world_name": None if package is None else package.name,
            "language": ui_language,
            "date_localized": story_day,
            "items": notes,
            "revealed_now": revealed_now,
            "letters": recent.get("turns", []),
            "at_checkpoint": bool(
                latest is not None and str(latest[0]) == "AT_CHECKPOINT"
            ),
        }

    def _world_actor_names(self, world_id: str) -> dict[str | None, str]:
        """One world's actor ids mapped to their card names (the
        signature resolution: ``world_actor → character_card.name``);
        ``None`` maps to the world's own byline. A card the table does
        not name falls back to the actor id — a plain signature, never a
        broken one."""

        names: dict[str | None, str] = {None: "世界"}
        try:
            rows = self._host.db.execute(
                "SELECT a.actor_id, c.name FROM world_actor a"
                " LEFT JOIN character_card c ON c.persona_id = a.persona_id"
                " WHERE a.world_id = ?",
                (world_id,),
            ).fetchall()
        except sqlite3.Error:
            return names
        for row in rows:
            actor_id = str(row[0])
            names[actor_id] = (
                str(row[1]) if row[1] not in (None, "") else actor_id
            )
        return names

    def _world_reveal_items(
        self, world_id: str, status: str
    ) -> tuple[WorldRevealItem, ...]:
        """The world's reveal items of one lifecycle word (wf-0), the
        store's own column order and record shape (the direct-SQL read
        posture — the store publishes no read face for the queue's two
        halves, and a read face here reads, never writes). The order is
        the event's own derivation order (``source_event_id`` ascending —
        ``<run_id>:<cursor>`` makes that the story's own order)."""

        rows = self._host.db.execute(
            "SELECT item_id, world_id, source_event_id, actor_id,"
            " status, revealed_at, created_at"
            " FROM world_reveal_item WHERE world_id = ? AND status = ?"
            " ORDER BY source_event_id ASC, item_id ASC",
            (world_id, status),
        ).fetchall()
        return tuple(
            WorldRevealItem(
                item_id=str(row[0]),
                world_id=str(row[1]),
                source_event_id=str(row[2]),
                actor_id=None if row[3] is None else str(row[3]),
                status=str(row[4]),
                revealed_at=None if row[5] is None else str(row[5]),
                created_at=str(row[6]),
            )
            for row in rows
        )

    def _world_notes_joined(
        self,
        world_id: str,
        package: WorldPackage | None,
        items: tuple[WorldRevealItem, ...],
    ) -> list[dict[str, Any]]:
        """The item→event join shared by the three world read faces
        (wf-0): each reveal item joined to its chronicle event (the
        pointer, never a copy — the inbox payload's own join shape), its
        narration in the interface language (:meth:`_note_narration` —
        the W-L law), its moment word, its signature (the comms actor's
        card name, ``None`` for the world's own narration), its reveal
        stamp, and the event's story day (the ``YYYY-MM-DD``
        discriminator; ``None`` for a legacy wall-clock row — an honest
        old row is never dressed up as a story day).

        A read-face helper: no write, no reveal, no clock — the caller
        decides what the notes are for."""

        ui_language = self._ui_language()
        by_id: dict[str, tuple[Any, ...]] = {}
        for row in self._host.db.execute(
            "SELECT e.event_id, e.narration, e.kind, e.occurred_at"
            " FROM world_event e WHERE e.world_id = ?",
            (world_id,),
        ).fetchall():
            by_id[str(row[0])] = tuple(row)
        actor_names = self._world_actor_names(world_id)
        notes: list[dict[str, Any]] = []
        for item in items:
            event = by_id.get(str(item.source_event_id))
            narration, fallback = self._note_narration(
                package, ui_language, event
            )
            occurred_at = "" if event is None else str(event[3])
            notes.append(
                {
                    "narration": narration,
                    "moment": "" if event is None else str(event[2]),
                    "signature": (
                        None
                        if item.actor_id is None
                        else actor_names.get(item.actor_id)
                    ),
                    "revealed_at": item.revealed_at,
                    "occurred_at": occurred_at,
                    "fallback": fallback,
                    "story_day": (
                        occurred_at
                        if _ISO_DAY_RE.fullmatch(occurred_at)
                        else None
                    ),
                }
            )
        return notes

    def _world_actor_cards(
        self, world_id: str
    ) -> list[tuple[Any, Any | None]]:
        """One world's actors joined to their character cards (wf-0), in
        the roster's own serving order — builtin first, then by card id
        (the card store's ``list_all`` order); a persona the card table
        does not name rides last, by actor id — a plain resident, never
        a broken one. The residents' rows and the overview's resident
        block read this one join, never a second roster."""

        world_store = getattr(self._host, "world_store", None)
        if world_store is None:
            return []
        read = self._require_cards().list_all()
        if isinstance(read, Err):
            raise RuntimeError(
                "the character roster could not be read:"
                f" {read.error.code.value}: {read.error.message}"
            )
        rank = {
            str(card.persona_id): index
            for index, card in enumerate(read.value)
        }
        joined: list[tuple[Any, Any | None]] = []
        for actor in world_store.actors_of(world_id):
            card = next(
                (
                    candidate
                    for candidate in read.value
                    if str(candidate.persona_id) == str(actor.persona_id)
                ),
                None,
            )
            joined.append((actor, card))
        joined.sort(
            key=lambda pair: (
                rank.get(str(pair[0].persona_id), len(rank)),
                str(pair[0].actor_id),
            )
        )
        return joined

    def _world_resident_face(
        self,
        binding: dict[str, Any],
        world_id: str,
    ) -> dict[str, Any] | None:
        """The overview's resident block (wf-0): the bound actor's card
        name and persona through the ``world_actor → character_card``
        join (:meth:`_world_actor_cards`) — ``None`` when the binding
        names no actor (the world's own narration; a ``NULL`` actor is
        honest, never a guessed resident)."""

        actor_id = binding["actor_id"]
        if actor_id is None:
            return None
        actor_id = str(actor_id)
        matched = next(
            (
                (actor, card)
                for actor, card in self._world_actor_cards(world_id)
                if str(actor.actor_id) == actor_id
            ),
            None,
        )
        if matched is None:
            # Unreachable while the binding's own FK stands — the honest
            # defensive answer is a plain id, never a guessed card.
            return {"actor_id": actor_id, "persona_id": None, "name": actor_id}
        actor, card = matched
        return {
            "actor_id": actor_id,
            "persona_id": str(actor.persona_id),
            "name": (
                actor_id
                if card is None or card.name in (None, "")
                else card.name
            ),
        }

    def _world_letter_count(self, conversation_id: str) -> int:
        """One conversation's letter count (wf-0): the user-visible
        window's turn count at unbounded breadth — the history face's own
        read family (the archive's filter, not a second transcript
        implementation). A conversation id the table does not carry
        answers 0 through the same read — nobody has written, and the
        count says so."""

        window = self._host.conversations.get_user_visible_conversation_window(
            ConversationId(conversation_id), -1
        )
        if isinstance(window, Err):
            raise RuntimeError(
                "the conversation window could not be read:"
                f" {window.error.code.value}: {window.error.message}"
            )
        return len(window.value.slices)

    def world_overview(self) -> tuple[int, dict[str, Any]]:
        """The world's one-screen read (wf-0): its name, its story day
        (derived, never clocked — :func:`elc.world.package.world_date_of`
        is the calendar's own law), today's revealed notes, and the
        resident this conversation's binding names.

        The read faces keep the inbox's own guards: no binding (this
        conversation lives in no world — or the host has no world leg) is
        the same **404**, the same sentence — a world overview that does
        not exist is not an empty one. The ``today`` block carries the
        ``REVEALED`` items whose event's story day is the world's today
        (the shared join, :meth:`_world_notes_joined`); a day with
        nothing said answers ``{"quiet": True, "note": …}`` — the
        quiet-day arm is an honest fact about today, never a disclosure
        of what still waits (the ``PENDING`` slice stays out of sight:
        reading is not opening, the reveal belongs to the inbox's
        presentation alone). The ``resident`` block is the bound actor's
        card name and persona; the world's own narration (a ``NULL``
        actor binding) answers ``None`` — nobody sits in the signature
        seat, and the face says so. Every answer carries the interface
        language it rendered in."""

        binding = self._world_binding()
        if binding is None:
            return (404, {"error": _WORLD_NO_BINDING})
        world_id = str(binding["world_id"])
        world_store = getattr(self._host, "world_store", None)
        if world_store is None:
            return (404, {"error": _WORLD_NO_BINDING})
        package = self._world_packages.get(world_id)
        ui_language = self._ui_language()
        world_name = None if package is None else package.name
        day = (
            world_date_of(package, world_store, world_id)
            if package is not None
            else ""
        )
        revealed = self._world_reveal_items(world_id, "REVEALED")
        todays = [
            note
            for note in self._world_notes_joined(world_id, package, revealed)
            if note["story_day"] == day
        ]
        today: dict[str, Any] = (
            {
                "quiet": True,
                "note": _WORLD_QUIET_DAY.get(
                    ui_language, _WORLD_QUIET_DAY["zh"]
                ),
            }
            if not todays
            else {"quiet": False, "items": todays}
        )
        return (
            200,
            {
                "world_id": world_id,
                "world_name": world_name,
                "date_localized": (
                    _localize_story_date(day, ui_language, world_name)
                    if day
                    else ""
                ),
                "ui_language": ui_language,
                "today": today,
                "resident": self._world_resident_face(binding, world_id),
            },
        )

    def world_log(self) -> tuple[int, dict[str, Any]]:
        """The world's revealed chronicle (wf-0), grouped by story day,
        newest day first — the read side of the reveal discipline.

        **The red line: this face never calls ``reveal_all``.** Reading
        the log is looking, not opening — 「看一眼」不等于「拆信」: a
        ``PENDING`` note is the world's unposted letter and stays out of
        every answer here (the SQL's own ``WHERE status = 'REVEALED'``);
        the only presentation triggers that flip the world's slice are
        the inbox's atomic reveal and the turn wiring's own presentation
        step. Each group is one story day (the event's ``YYYY-MM-DD``
        stamp, :meth:`_world_notes_joined`'s join; a legacy wall-clock
        row has no story day and answers ``date_localized: None``, last —
        an honest old row is never dressed up as a story day), the items
        in the durable order (event id ascending). No binding is the
        same **404**, the same sentence, as the inbox's."""

        binding = self._world_binding()
        if binding is None:
            return (404, {"error": _WORLD_NO_BINDING})
        world_id = str(binding["world_id"])
        world_store = getattr(self._host, "world_store", None)
        if world_store is None:
            return (404, {"error": _WORLD_NO_BINDING})
        package = self._world_packages.get(world_id)
        ui_language = self._ui_language()
        revealed = self._world_reveal_items(world_id, "REVEALED")
        grouped: dict[str, list[dict[str, Any]]] = {}
        for note in self._world_notes_joined(world_id, package, revealed):
            grouped.setdefault(str(note["story_day"] or ""), []).append(note)
        days: list[dict[str, Any]] = []
        for day in sorted(grouped, reverse=True):
            days.append(
                {
                    "date_localized": (
                        None
                        if day == ""
                        else _localize_story_date(day, ui_language)
                    ),
                    "items": [
                        {
                            "narration": note["narration"],
                            "moment": note["moment"],
                            "signature": note["signature"],
                            "revealed_at": note["revealed_at"],
                            "fallback": note["fallback"],
                        }
                        for note in grouped[day]
                    ],
                }
            )
        return (
            200,
            {
                "world_id": world_id,
                "world_name": None if package is None else package.name,
                "ui_language": ui_language,
                "days": days,
            },
        )

    def world_residents(self) -> tuple[int, dict[str, Any]]:
        """The bound world's residents (wf-0): every cast actor joined to
        its character card — name, identity line, persona — with the
        conversation's own resident marked, and each resident's letter
        count (the user-visible turns of the conversations bound to that
        actor, :meth:`_world_letter_count`'s read family; an actor with
        no bound conversation answers 0 — nobody has written them, and
        the face says so).

        The order is the roster's own (builtin first,
        :meth:`_world_actor_cards`); ``is_current`` marks exactly the
        bound actor (all false when the binding names none). No binding
        is the same **404**, the same sentence, as the inbox's. A read
        face: it flips nothing and counts only what is already
        delivered."""

        binding = self._world_binding()
        if binding is None:
            return (404, {"error": _WORLD_NO_BINDING})
        world_id = str(binding["world_id"])
        world_store = getattr(self._host, "world_store", None)
        if world_store is None:
            return (404, {"error": _WORLD_NO_BINDING})
        package = self._world_packages.get(world_id)
        bindings_by_actor: dict[str, list[str]] = {}
        for record in world_store.conversations_of(world_id):
            bindings_by_actor.setdefault(str(record.actor_id), []).append(
                str(record.conversation_id)
            )
        residents: list[dict[str, Any]] = []
        for actor, card in self._world_actor_cards(world_id):
            residents.append(
                {
                    "actor_id": str(actor.actor_id),
                    "persona_id": str(actor.persona_id),
                    "name": (
                        str(actor.actor_id)
                        if card is None or card.name in (None, "")
                        else card.name
                    ),
                    "identity": "" if card is None else card.identity,
                    "is_current": (
                        binding["actor_id"] is not None
                        and str(actor.actor_id) == str(binding["actor_id"])
                    ),
                    "letters_count": sum(
                        self._world_letter_count(conversation_id)
                        for conversation_id in bindings_by_actor.get(
                            str(actor.actor_id), []
                        )
                    ),
                }
            )
        return (
            200,
            {
                "world_id": world_id,
                "world_name": None if package is None else package.name,
                "ui_language": self._ui_language(),
                "residents": residents,
            },
        )

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
          (:func:`_partner_card_face`), resolved for the conversation this
          face serves: a conversation that names a roster card reads the
          card table (queue ④ — the dossier follows the switch); one that
          names none falls back to :data:`PENPAL_CHARACTER_PACKAGE` — the
          single-source rule holds server-side too (the page never spells
          a value of the character, this face never spells a second
          copy);
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
        served = _character_of_conversation(conversation)
        served_record: CharacterCardRecord | None = None
        if served is not None:
            read = self._require_cards().get(served)
            if not isinstance(read, Err):
                served_record = read.value
        return {
            "card": _partner_card_face(served_record),
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
        shelf). The lifecycle words come off the official family (queue
        ④ — all four cards carry the same pair, the family head is
        quoted, no second spelling), the revision starts at 1, the card
        is born ``is_builtin: False`` — a user card can be edited and
        deleted like any other user card."""

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
            generation_policy=(
                OFFICIAL_CHARACTER_PACKAGES[0].generation_policy
            ),
            lore_refs=(),
            revision=1,
            status=OFFICIAL_CHARACTER_PACKAGES[0].status,
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
        """Remove one user-authored card (MC-0) — the builtins are refused.

        ``AUTHORITY_VIOLATION`` (the official family — the penpal and the
        companions seeded beside her — is not this store's to end) rides
        409, an unknown id 404. Deleting retires the card from the
        roster; the conversation and the memories it earned stay (history
        is not rewritten here — the deeper walk is BF-05's business, out
        of this cut's scope)."""

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

    def _effective_stage(self) -> RolloutStage | None:
        """The tier the **next** turn decides under — the live reading.

        The veto-response cut's read order for faces: the coordinator's
        current wiring's ``rollout_stage`` when the automatic leg is
        assembled (the hot change swaps that wiring, so this is the truth
        the page must show), else the host's open-time snapshot (the
        prep-1 tier's shape — no wiring, the persisted word's display
        reading). ``None`` stays ``None``: the fail-closed default is a
        fact, never a stage this face substitutes.
        """

        wiring = self._host.coordinator.automatic_teaching_wiring()
        if wiring is not None:
            return wiring.rollout_stage
        return getattr(self._host, "rollout_stage", None)

    def settings(self) -> dict[str, Any]:
        """The settings section's one read (主线-1) — three faces of live
        truth in one payload.

        Read-only, on the work queue (the diagnostics construction). The
        three faces: ``rollout_stage`` is the **effective** tier — the live
        wiring's stage when the automatic leg is assembled (which the
        page's mode write moves), else the host's open-time snapshot;
        ``None`` stays ``None`` (the fail-closed default is a fact about
        the launch, never a stage this face substitutes);
        the §5.1 policy row when one exists (``null`` when none does —
        before a first write there is nothing to read, never a fabricated
        policy); the §5.1 disclosure row through the store's own existing
        read face (:meth:`elc.user_config.store.SqliteUserConfigStore.
        get_disclosure_policy` — the same row the controller's disclosure
        decision consults, shown as it stands, no second reading). The
        three vocabularies the editors need ride server-declared (the
        frequency words, the whitelist itself, and the four §12 stage
        words — the page copies no word list). A host without the
        user-config leg answers
        ``available: false`` with the stage still riding (the stage is the
        host's, not the user-config leg's) and both rows
        honestly ``null``. An unreadable row is a server fact (the route's
        500 posture). W-L: the payload also carries the two language
        words — ``ui_language`` (default ``zh``) and ``reply_language``
        (default ``follow``), the stored row or the default, never a row
        written by a read — plus the two whitelists, server-declared like
        every vocabulary the editors consume (the page copies no word
        list).
        """

        stage = self._effective_stage()
        stage_value = None if stage is None else str(stage.value)
        controller = self._host.user_config
        frequency_words = list(_FREQUENCY_WORDS)
        disclosure_levels = [level.value for level in DisclosureLevel]
        mode_words = list(_MODE_WORDS)
        provider = self._provider_face_with_profiles()
        # W-L: the two language words — the stored row, or the default
        # when nothing is chosen yet (an absent row answers the default
        # and writes nothing; the read substitutes, the store never
        # does). The whitelists ride so the page copies no word list.
        ui_language = self._host.app_settings.get(APP_SETTING_UI_LANGUAGE_KEY)
        reply_language = self._host.app_settings.get(
            APP_SETTING_REPLY_LANGUAGE_KEY
        )
        if controller is None or self._host.user_id is None:
            return {
                "available": False,
                "rollout_stage": stage_value,
                "provider": provider,
                "teaching_policy": None,
                "disclosure": None,
                "frequency_words": frequency_words,
                "disclosure_levels": disclosure_levels,
                "mode_words": mode_words,
                "writable_knobs": list(_SETTINGS_KNOBS),
                "ui_language": ui_language or "zh",
                "reply_language": reply_language or "follow",
                "ui_language_words": list(_UI_LANGUAGE_WORDS),
                "reply_language_words": list(RESPONSE_LANGUAGE_WORDS),
            }
        user_id = self._host.user_id
        policy = controller.get_teaching_policy(user_id)
        if isinstance(policy, Err):
            raise RuntimeError(
                "the teaching policy could not be read:"
                f" {policy.error.code.value}: {policy.error.message}"
            )
        store = getattr(self._host, "user_config_store", None)
        if store is None:
            # Unreachable in production assembly (the controller and its
            # store are built together); a test double that carries one
            # without the other gets the loud refusal, never a fabricated
            # "no rules".
            raise RuntimeError(
                "the disclosure policy could not be read:"
                " this host carries a user-config controller without its"
                " store"
            )
        disclosure = store.get_disclosure_policy(user_id)
        if isinstance(disclosure, Err):
            raise RuntimeError(
                "the disclosure policy could not be read:"
                f" {disclosure.error.code.value}: {disclosure.error.message}"
            )
        return {
            "available": True,
            "rollout_stage": stage_value,
            "provider": provider,
            "teaching_policy": (
                None
                if policy.value is None
                else _settings_policy_face(policy.value)
            ),
            "disclosure": (
                None
                if disclosure.value is None
                else _settings_disclosure_face(disclosure.value)
            ),
            "frequency_words": frequency_words,
            "disclosure_levels": disclosure_levels,
            "mode_words": mode_words,
            "writable_knobs": list(_SETTINGS_KNOBS),
            "ui_language": ui_language or "zh",
            "reply_language": reply_language or "follow",
            "ui_language_words": list(_UI_LANGUAGE_WORDS),
            "reply_language_words": list(RESPONSE_LANGUAGE_WORDS),
        }

    def _provider_face_with_profiles(
        self,
    ) -> dict[str, Any] | None:
        """The live provider face plus the model-profile roster (the
        multi-model cut, user direction: several saved models switched any
        time).

        The roster rides the same ``provider`` object so the page reads one
        shape: ``profiles`` (id / name / base_url / model / api_key_set —
        the key's **value** is never in any read face) and
        ``active_profile`` (the id the live pair came from, ``None`` for
        custom edits / launch args). A row the strict write face could not
        have written (hand-edited, corrupt) is omitted, never guessed into
        a profile.
        """

        face = self._host.provider_face()
        if face is None:
            return None
        profiles: list[dict[str, Any]] = []
        for key, value in self._host.app_settings.items(
            APP_SETTING_PROVIDER_PROFILE_PREFIX
        ):
            profile_id = key[len(APP_SETTING_PROVIDER_PROFILE_PREFIX):]
            try:
                doc = json.loads(value)
            except ValueError:
                continue
            if not isinstance(doc, dict):
                continue
            name = doc.get("name")
            base_url = doc.get("base_url")
            model = doc.get("model")
            api_key = doc.get("api_key")
            if not (
                isinstance(name, str)
                and name
                and isinstance(base_url, str)
                and base_url
                and isinstance(model, str)
                and model
            ):
                continue
            profiles.append(
                {
                    "id": profile_id,
                    "name": name,
                    "base_url": base_url,
                    "model": model,
                    "api_key_set": isinstance(api_key, str)
                    and bool(api_key),
                }
            )
        active = self._host.app_settings.get(
            APP_SETTING_PROVIDER_ACTIVE_PROFILE_KEY
        )
        merged = dict(face)
        merged["profiles"] = profiles
        merged["active_profile"] = active or None
        return merged

    def _provider_profile_doc(self, profile_id: str) -> dict[str, Any] | None:
        """One profile's stored document, or ``None`` when absent/corrupt."""

        raw = self._host.app_settings.get(
            APP_SETTING_PROVIDER_PROFILE_PREFIX + profile_id
        )
        if raw is None:
            return None
        try:
            doc = json.loads(raw)
        except ValueError:
            return None
        return doc if isinstance(doc, dict) else None

    def provider_profile_save(
        self,
        profile_id: str | None,
        name: str,
        base_url: str,
        model: str,
        api_key: str | None,
    ) -> tuple[int, dict[str, Any]]:
        """The profile write (multi-model cut): create or update one named
        model profile under ``provider_profile:<id>``.

        The grammar was validated at the HTTP layer; an explicit ``id``
        updates that profile in place (an absent ``api_key`` keeps the
        stored one — the same ride-along rule as the main face), an absent
        id mints one. The row is strict JSON written only here; activating
        is the other face's job (this write moves no live object).
        """

        face = self._host.provider_face()
        if face is None:
            return (
                200,
                {
                    "accepted": False,
                    "id": None,
                    "error": (
                        "这个进程不是 OpenAI 兼容装配——配置档没有可生效的"
                        "地方，什么都没写。"
                    ),
                },
            )
        pid = profile_id if profile_id else "p" + uuid.uuid4().hex[:10]
        key = APP_SETTING_PROVIDER_PROFILE_PREFIX + pid
        # unique names (self-audit item): two chips reading 「本地推理」 is
        # user-facing ambiguity — a duplicate name is a 200 人话 refusal
        # (updating a profile under its own id keeps its own name, of course)
        for other_key, other_value in self._host.app_settings.items(
            APP_SETTING_PROVIDER_PROFILE_PREFIX
        ):
            other_id = other_key[len(APP_SETTING_PROVIDER_PROFILE_PREFIX):]
            if other_id == pid:
                continue
            try:
                other_doc = json.loads(other_value)
            except ValueError:
                continue
            if (
                isinstance(other_doc, dict)
                and other_doc.get("name") == name
            ):
                return (
                    200,
                    {
                        "accepted": False,
                        "id": None,
                        "error": (
                            "已有同名配置档——换个名字，或先删掉旧的"
                            "（名字是切换时认档的唯一面）。"
                        ),
                    },
                )
        if api_key is None:
            stored = self._provider_profile_doc(pid)
            if stored is not None and isinstance(
                stored.get("api_key"), str
            ) and stored.get("api_key"):
                api_key = str(stored.get("api_key"))
        doc = {
            "name": name,
            "base_url": base_url,
            "model": model,
            "api_key": api_key,
        }
        self._host.app_settings.set(
            key, json.dumps(doc, ensure_ascii=False)
        )
        return (200, {"accepted": True, "id": pid, "error": None})

    def provider_profile_activate(
        self, profile_id: str
    ) -> tuple[int, dict[str, Any]]:
        """The switch face: apply one profile as the live provider.

        Same order as the main provider write — the profile's key first
        (when it carries one; an absent key leaves the current active key
        in place), then the hot swap (the *next* letter dials the new
        destination), then the pair persists and the active pointer names
        the profile. Activating the already-live profile answers
        ``idempotent`` and writes nothing.
        """

        face = self._host.provider_face()
        if face is None:
            return (
                200,
                {
                    "accepted": False,
                    "idempotent": False,
                    "error": (
                        "这个进程不是 OpenAI 兼容装配——切换没有可生效的地方。"
                    ),
                },
            )
        doc = self._provider_profile_doc(profile_id)
        if (
            doc is None
            or not isinstance(doc.get("base_url"), str)
            or not doc.get("base_url")
            or not isinstance(doc.get("model"), str)
            or not doc.get("model")
        ):
            return (
                200,
                {
                    "accepted": False,
                    "idempotent": False,
                    "error": "没有这个配置档——先存一个，再切换。",
                },
            )
        final_base = str(doc["base_url"])
        final_model = str(doc["model"])
        active = self._host.app_settings.get(
            APP_SETTING_PROVIDER_ACTIVE_PROFILE_KEY
        )
        if (
            active == profile_id
            and face["base_url"] == final_base
            and face["model"] == final_model
        ):
            return (
                200,
                {
                    "accepted": True,
                    "idempotent": True,
                    "error": None,
                },
            )
        profile_key = doc.get("api_key")
        if isinstance(profile_key, str) and profile_key:
            # the key first: the swap's send-time source reads the store
            self._host.app_settings.set(
                APP_SETTING_PROVIDER_API_KEY_KEY, profile_key
            )
        refusal = self._host.replace_provider(final_base, final_model)
        if refusal is not None:
            return (
                200,
                {
                    "accepted": False,
                    "idempotent": False,
                    "error": refusal,
                },
            )
        self._host.app_settings.set(
            APP_SETTING_PROVIDER_BASE_URL_KEY, final_base
        )
        self._host.app_settings.set(
            APP_SETTING_PROVIDER_MODEL_KEY, final_model
        )
        self._host.app_settings.set(
            APP_SETTING_PROVIDER_ACTIVE_PROFILE_KEY, profile_id
        )
        return (
            200,
            {
                "accepted": True,
                "idempotent": False,
                "error": None,
            },
        )

    def provider_profile_delete(
        self, profile_id: str
    ) -> tuple[int, dict[str, Any]]:
        """The roster write: remove one profile (idempotent — an absent id
        is fine). Deleting the active profile leaves the live pair serving
        (it is still the configuration in force) and the pointer returns to
        custom (``None``) — nothing hot-swaps on a delete.
        """

        self._host.app_settings.delete(
            APP_SETTING_PROVIDER_PROFILE_PREFIX + profile_id
        )
        active = self._host.app_settings.get(
            APP_SETTING_PROVIDER_ACTIVE_PROFILE_KEY
        )
        if active == profile_id:
            self._host.app_settings.set(
                APP_SETTING_PROVIDER_ACTIVE_PROFILE_KEY, ""
            )
        return (200, {"accepted": True, "error": None})

    def mode_save(self, stage_word: str) -> tuple[int, dict[str, Any]]:
        """The tier write (veto-response cut): persist the §12 word, then
        move the live wiring.

        The grammar was validated at the HTTP layer (the four-word
        whitelist, case-sensitive) and is re-derived here only to fail
        closed — the :class:`~elc.teaching.rollout.RolloutStage`
        construction cannot be talked past the enum. Two writes, in this
        order: the word goes into ``app_setting`` (migration 0022's table —
        the durable half, what the next open reads when the launch command
        declares nothing), then the coordinator receives a **new** wiring
        whose ``rollout_stage`` moved (:func:`dataclasses.replace` over the
        frozen dataclass — every face rides verbatim), so the next turn
        decides under the new tier with no reassembly. The host's frozen
        ``rollout_stage`` snapshot is untouched (it documents the open);
        the settings read answers from the live wiring. An unchanged word
        answers ``idempotent`` and writes nothing; a host without the
        automatic leg (the prep-1 tier) is a runtime fact — 200 +
        ``accepted: false``, the honest sentence, nothing persisted (a
        write with nothing to move would only fork the next open's tier
        from this process's truth). The gate functions are untouched; the
        default ``None`` still DENIES automatic teaching.
        """

        try:
            stage = RolloutStage(stage_word)
        except ValueError:
            return (400, {"accepted": False, "error": _MODE_GRAMMAR})
        wiring = self._host.coordinator.automatic_teaching_wiring()
        if wiring is None:
            return (
                200,
                {
                    "accepted": False,
                    "idempotent": False,
                    "stage": stage.value,
                    "error": (
                        "这个进程没有装内容库腿（--content-db）——教学档位"
                        "没有可生效的地方。带上 --content-db 重启后，档位"
                        "就能在这里改，改完即热生效。"
                    ),
                },
            )
        if wiring.rollout_stage == stage:
            return (
                200,
                {
                    "accepted": True,
                    "idempotent": True,
                    "stage": stage.value,
                    "error": None,
                },
            )
        self._host.app_settings.set(
            APP_SETTING_ROLLOUT_STAGE_KEY, stage.value
        )
        moved = dataclasses.replace(wiring, rollout_stage=stage)
        self._host.coordinator.replace_automatic_teaching(moved)
        return (
            200,
            {
                "accepted": True,
                "idempotent": False,
                "stage": stage.value,
                "error": None,
            },
        )

    def _language_word_save(
        self, key: str, word: str
    ) -> tuple[int, dict[str, Any]]:
        """The shared half of the two language writes (W-L): persist one
        whitelisted word under its ``app_setting`` key, idempotently.

        The grammar was validated at the HTTP layer and re-checked here
        against the same tuple — a word outside it cannot reach this
        store (the mode write's fail-closed re-derivation, restated).
        One upsert; an unchanged word answers ``idempotent`` and writes
        nothing. The very next reader sees the new word: the
        coordinator's reply-language port reads the row per turn (no
        reassembly), and the inbox read answers the ui-language row per
        request — a hot change like the provider pair's, with nothing to
        swap because the readers are per-turn reads, not held objects.
        """

        current = self._host.app_settings.get(key)
        if current == word:
            return (
                200,
                {"accepted": True, "idempotent": True, "error": None},
            )
        self._host.app_settings.set(key, word)
        return (
            200,
            {"accepted": True, "idempotent": False, "error": None},
        )

    def ui_language_save(self, word: str) -> tuple[int, dict[str, Any]]:
        """The interface-language write (W-L): ``zh`` / ``en`` — the page's
        own presentation word (today: the world inbox's bilingual face;
        full-page i18n is registered out of scope). The inbox payload
        reads this row per request, so the next
        ``GET /api/world/inbox`` renders in the new language."""

        if word not in _UI_LANGUAGE_WORDS:
            return (400, {"accepted": False, "error": _UI_LANGUAGE_GRAMMAR})
        status, body = self._language_word_save(
            APP_SETTING_UI_LANGUAGE_KEY, word
        )
        body["ui_language"] = word
        return status, body

    def reply_language_save(self, word: str) -> tuple[int, dict[str, Any]]:
        """The reply-language write (W-L): ``zh`` / ``en`` / ``follow`` —
        the ``[response]`` section's language-row word. The coordinator's
        best-effort port reads this row on the very next compilation (no
        reassembly), so the next letter answers in the chosen language;
        ``follow`` restores the pre-W-L stance."""

        if word not in RESPONSE_LANGUAGE_WORDS:
            return (400, {"accepted": False, "error": _REPLY_LANGUAGE_GRAMMAR})
        status, body = self._language_word_save(
            APP_SETTING_REPLY_LANGUAGE_KEY, word
        )
        body["reply_language"] = word
        return status, body

    def provider_save(
        self,
        base_url: str | None,
        model: str | None,
        api_key: str | None = None,
    ) -> tuple[int, dict[str, Any]]:
        """The provider write (user veto: endpoint/model/key are page facts).

        The HTTP layer validated the body's grammar (one or more of the
        three keys, well-formed); here the pair resolves against the live
        config — an absent key rides the live value — and refuses before any
        write when the destination is a plaintext non-loopback http URL the
        live config's opt-in does not cover (the launch command's own rule;
        the page grants no second, weaker rule) or the host's provider is
        not OpenAI-shaped (a test double — 200 + ``accepted: false``, the
        honest sentence, nothing persisted). Writes, in order: the **key
        first** (an independent setting — the hot swap's send-time source
        reads it), then the host swaps the live provider, then the pair
        persists — so the *next* letter dials the new destination with the
        new key and no restart. A body that changes nothing answers
        ``idempotent`` and writes nothing. The key's value is never in any
        read face (``api_key_set`` alone) and never compared outside this
        write path; it lives in the local single-user app.db and nowhere
        else.
        """

        face = self._host.provider_face()
        if face is None:
            return (
                200,
                {
                    "accepted": False,
                    "idempotent": False,
                    "provider": None,
                    "error": (
                        "这个进程不是 OpenAI 兼容装配——换端点没有可生效的"
                        "地方，什么都没写。"
                    ),
                },
            )
        live_base = str(face["base_url"])
        live_model = str(face["model"])
        final_base = live_base if base_url is None else base_url
        final_model = live_model if model is None else model
        saved_key = self._host.app_settings.get(
            APP_SETTING_PROVIDER_API_KEY_KEY
        )
        key_unchanged = api_key is None or api_key == saved_key
        if (
            final_base == live_base
            and final_model == live_model
            and key_unchanged
        ):
            return (
                200,
                {
                    "accepted": True,
                    "idempotent": True,
                    "provider": face,
                    "error": None,
                },
            )
        if api_key is not None and not key_unchanged:
            # the key first: the swap's send-time source reads the store
            self._host.app_settings.set(
                APP_SETTING_PROVIDER_API_KEY_KEY, api_key
            )
        refusal = self._host.replace_provider(final_base, final_model)
        if refusal is not None:
            return (
                200,
                {
                    "accepted": False,
                    "idempotent": False,
                    "provider": face,
                    "error": refusal,
                },
            )
        self._host.app_settings.set(
            APP_SETTING_PROVIDER_BASE_URL_KEY, final_base
        )
        self._host.app_settings.set(APP_SETTING_PROVIDER_MODEL_KEY, final_model)
        # manual edits diverge from any profile — the pointer returns to
        # custom (the multi-model cut's honesty rule: the pointer names
        # where the live pair came from, and after this it came from here)
        self._host.app_settings.set(
            APP_SETTING_PROVIDER_ACTIVE_PROFILE_KEY, ""
        )
        return (
            200,
            {
                "accepted": True,
                "idempotent": False,
                "provider": {
                    "base_url": final_base,
                    "model": final_model,
                    "api_key_set": (
                        api_key is not None
                        or self._host.app_settings.get(
                            APP_SETTING_PROVIDER_API_KEY_KEY
                        )
                        is not None
                    ),
                },
                "error": None,
            },
        )

    def teaching_policy_save(
        self, knobs: dict[str, Any]
    ) -> tuple[int, dict[str, Any]]:
        """The settings section's one write (主线-1): the eight §5.1 knobs
        as the full new set, everything else verbatim.

        The grammar was validated at the HTTP layer (the whitelist, the
        four frequency words, string-or-null per knob) and is re-derived
        here only to fail closed — the
        :class:`~elc.user_config.types.TeachingFrequency` construction
        cannot be talked past the enum. The durable row's non-knob columns
        are rebuilt exactly as they read (``mode`` / ``effective_from``
        preserved — the F-4 ``""`` sentinel on the first write, no clock
        value invented; ``updated_at`` is the store's own clock) and the
        version moves by :func:`_next_version`. An unchanged knob set
        answers 200 with ``idempotent`` and writes nothing (no empty
        version churn); a ``CONFLICT`` rides 409 like the goal writes; any
        other refusal is a runtime fact (200 + ``accepted: false``). The
        write moves how/how-often configuration only — never the rollout
        tier (``mode`` is not a knob), never an 开闸 face.
        """

        controller = self._host.user_config
        if controller is None or self._host.user_id is None:
            return (200, _no_user_config_answer())
        user_id = self._host.user_id
        try:
            frequency = TeachingFrequency(str(knobs["teaching_frequency"]))
        except (KeyError, ValueError):
            return (
                400,
                {
                    "accepted": False,
                    "conflict": False,
                    "error": _SETTINGS_FREQUENCY_GRAMMAR,
                },
            )
        current = controller.get_teaching_policy(user_id)
        if isinstance(current, Err):
            raise RuntimeError(
                "the teaching policy could not be read:"
                f" {current.error.code.value}: {current.error.message}"
            )
        policy_now = current.value
        if policy_now is not None:
            unchanged = policy_now.teaching_frequency is frequency and all(
                getattr(policy_now, knob) == knobs[knob]
                for knob in _SETTINGS_KNOBS[1:]
            )
            if unchanged:
                return (
                    200,
                    {
                        "accepted": True,
                        "idempotent": True,
                        "policy_version": str(policy_now.policy_version),
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
                interruption_budget=knobs["interruption_budget"],
                curriculum_initiative=knobs["curriculum_initiative"],
                correction_strictness=knobs["correction_strictness"],
                hint_policy=knobs["hint_policy"],
                assessment_visibility=knobs["assessment_visibility"],
                practice_density=knobs["practice_density"],
                persona_freedom=knobs["persona_freedom"],
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
                "conflict": False,
                "error": None,
            },
        )

    def disclosure_save(
        self, payload: Any
    ) -> tuple[int, dict[str, Any]]:
        """The disclosure section's one write (fr-A): the full new rule set
        for the §5.1 DisclosurePolicy, versioned like the policy writes.

        The grammar was validated at the HTTP layer
        (:func:`_disclosure_request_rules`) and is re-derived here only to
        fail closed — the ``DisclosureLevel`` construction cannot be talked
        past the enum. The row's key is the user's own id (the Local V1
        linking convention); the revision moves by :func:`_next_version`.
        An unchanged rule set answers 200 with ``idempotent`` and writes
        nothing (no empty revision churn); a ``CONFLICT`` rides 409 like
        the goal/policy writes; any other refusal is a runtime fact (200 +
        ``accepted: false``). The write moves what personas may be told
        about the user only — never a profile fact, never the rollout
        tier.
        """

        controller = self._host.user_config
        if controller is None or self._host.user_id is None:
            return (200, _no_user_config_answer())
        error, rules = _disclosure_request_rules(payload)
        if error is not None or rules is None:
            return (
                400,
                {
                    "accepted": False,
                    "conflict": False,
                    "error": error or "the disclosure body is out of grammar",
                },
            )
        user_id = self._host.user_id
        store = getattr(self._host, "user_config_store", None)
        if store is None:
            raise RuntimeError(
                "the disclosure policy could not be read:"
                " this host carries a user-config controller without its"
                " store"
            )
        current = store.get_disclosure_policy(user_id)
        if isinstance(current, Err):
            raise RuntimeError(
                "the disclosure policy could not be read:"
                f" {current.error.code.value}: {current.error.message}"
            )
        policy_now = current.value
        new_rules = tuple(rules)
        if policy_now is not None and policy_now.rules == new_rules:
            return (
                200,
                {
                    "accepted": True,
                    "idempotent": True,
                    "revision": str(policy_now.revision),
                    "conflict": False,
                    "error": None,
                },
            )
        revision = _next_version(
            None if policy_now is None else str(policy_now.revision)
        )
        written = controller.set_disclosure_policy(
            DisclosurePolicy(
                disclosure_policy_id=str(user_id),
                revision=revision,
                rules=new_rules,
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
                "revision": str(written.value.revision),
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

    def history(
        self, full: bool = False, limit: int | None = None
    ) -> dict[str, Any]:
        """The canonical transcript window — what the page recovers on load.

        The store's user-visible window read (cs-0 处置 M-1: the *user* may
        read back every delivered assistant turn, the teaching letters
        included — the composed delivery text travels whole; the
        role-visible filter that keeps those texts from the persona's
        history stays on ``get_conversation_window`` and never touches this
        face). Delivered assistant output only; teaching command turns never
        appear; oldest first.

        主线-2 adds the explicit breadth parameters over the same
        user-visible filter family, the display semantics untouched:

        - no parameter — the unchanged :data:`HISTORY_TURNS` default window;
        - ``?limit=N`` — the ``N`` most recent turns through the identical
          read (the grammar in :func:`_history_request`);
        - ``?full=1`` — the whole user-visible transcript: the same window
          filter at unbounded breadth, the user-visible mirror of the cs-3
          full-history relation. The cs-3 face itself
          (``get_full_persona_visible_history``) stays persona-visible — its
          assistant-side filter keeps teaching letters out, which is the
          role's reading, not the archive's; the unbounded breadth here
          rides the same user-visible face's ``LIMIT ?`` with a negative
          bound (SQLite's documented no-limit reading), so the archive
          cannot silently change filter between the default window and the
          full read.

        ``has_more`` is the honest pagination bit: a bounded read fetches
        one row past its bound to answer it (a bound-sized answer is
        ambiguous by itself); an unbounded read is never ``true``. The
        per-turn shape and the default-window answer are exactly what they
        were — the two extra payload keys are additive.
        """

        bound: int | None
        if full:
            bound = None
        elif limit is not None:
            bound = limit
        else:
            bound = HISTORY_TURNS
        window = self._host.conversations.get_user_visible_conversation_window(
            self._conversation_id, -1 if bound is None else bound + 1
        )
        if isinstance(window, Err):
            raise RuntimeError(
                "the conversation window could not be read:"
                f" {window.error.code.value}: {window.error.message}"
            )
        slices = list(window.value.slices)
        if bound is None:
            has_more = False
        else:
            has_more = len(slices) > bound
            if has_more:
                # the store answers oldest-first; the bound-sized answer is
                # the most recent tail of the bound+1 it fetched
                slices = slices[len(slices) - bound :]
        # fr-A: the window's per-turn usage and the conversation-wide
        # cumulative — additive payload keys (the 主线-2 breadth keys'
        # precedent); both are read-only sums over the durable attempt rows.
        usage_by_turn = _usage_by_turn(
            self._host.db, [str(slice_.turn_id) for slice_ in slices]
        )
        turns: list[dict[str, Any]] = []
        for slice_ in slices:
            assistant = (
                None
                if slice_.assistant_turn is None
                else slice_.assistant_turn.content
            )
            turns.append(
                {
                    "user": slice_.user_turn.raw_content,
                    "assistant": assistant,
                    # The affordance bitmaps per side (v3-3), the same
                    # rows the turn response carries — ``None`` keeps
                    # every word clickable.
                    "user_word_hits": _letter_hit_rows(
                        slice_.user_turn.raw_content, self._lemma_runs
                    ),
                    "word_hits": (
                        None
                        if assistant is None
                        else _letter_hit_rows(assistant, self._lemma_runs)
                    ),
                    # fr-A: this turn's measured token usage, ``None`` when
                    # its attempts reported none — never a fabricated 0.
                    "usage": usage_by_turn.get(str(slice_.turn_id)),
                }
            )
        return {
            "turns": turns,
            "window": bound,
            "has_more": has_more,
            # fr-A: the conversation-wide cumulative (window-independent).
            "usage": _usage_totals(self._host.db, str(self._conversation_id)),
        }

    def schedule(self) -> dict[str, Any]:
        """The review-schedule zone's read — the Scheduler's own view.

        The classified :class:`~elc.scheduler.types.ScheduleView` at one
        ``as_of`` (now): every current §5.2 row in the bucket its window
        names — due / overdue / upcoming — each row passed through
        verbatim (:func:`_schedule_item_face`; the window pair, the spacing
        stage and the urgency are the row's own numbers, never a derived
        due-ness). The due decision is the Scheduler's and only the
        Scheduler's (D-INV-009), so a host without the scheduler leg
        answers the honest ``{"available": false}`` shape — the empty
        buckets of an unassembled authority, never a raw-table stand-in
        that would classify outside §9. Rows with no window
        (``NOT_SCHEDULED``) appear in no bucket: the view's own membership
        rule, relayed as-is. Read-only on the work queue (the diagnostics
        construction); a view that cannot be read is a server fact (the
        route's 500 posture).
        """

        scheduler = self._host.scheduler
        if scheduler is None:
            return {
                "available": False,
                "as_of": None,
                "due": [],
                "overdue": [],
                "upcoming": [],
            }
        view = scheduler.get_schedule_view(datetime.now(tz=UTC).isoformat())
        if isinstance(view, Err):
            raise RuntimeError(
                "the schedule view could not be read:"
                f" {view.error.code.value}: {view.error.message}"
            )
        classified = view.value
        return {
            "available": True,
            "as_of": classified.as_of,
            "schedule_version": str(classified.schedule_version),
            "due": [
                _schedule_item_face(item) for item in classified.due_items
            ],
            "overdue": [
                _schedule_item_face(item) for item in classified.overdue_items
            ],
            "upcoming": [
                _schedule_item_face(item) for item in classified.upcoming
            ],
        }

    def target_footprint(self, target_id: str) -> dict[str, Any]:
        """One expression's cross-letter footprint — the learning evidence
        the target left, distributed over the turns that produced it.

        The aggregate reads ``evidence_claim`` (the durable ledger,
        migration 0004) grouped by the claim's source turn: per turn the
        claim count and the outcomes exactly as the evaluator wrote them,
        ordered by the turn's durable sequence with the ledger's own
        ``rowid`` breaking ties — one deterministic answer to one world (a
        claim whose source turn row is unreachable keeps its place honestly
        with a ``null`` sequence — the ``LEFT JOIN`` never drops a claim for
        a missing join partner). Only ``ACTIVE`` rows count (STATE_MACHINES
        §18: only ACTIVE evidence enters estimation — the field name carries
        the reading); superseded or invalidated rows are not a footprint.
        A target with no evidence answers ``{"found": false}`` with an
        empty distribution — a 200 fact (the word lookup's posture),
        never a 404. Read-only SQL over ``host.db`` on the work queue
        (the diagnostics construction); nothing here writes, ever.
        """

        rows = self._host.db.execute(
            "SELECT ec.source_turn_id, ec.conversation_id, ec.outcome,"
            " u.turn_sequence FROM evidence_claim AS ec"
            " LEFT JOIN user_turn AS u ON u.turn_id = ec.source_turn_id"
            " WHERE ec.target_id = ? AND ec.status = 'ACTIVE'"
            " ORDER BY (u.turn_sequence IS NULL), u.turn_sequence,"
            " ec.source_turn_id, ec.rowid",
            (target_id,),
        ).fetchall()
        turns: list[dict[str, Any]] = []
        index_of: dict[str, int] = {}
        for turn_id, conversation_id, outcome, sequence in rows:
            position = index_of.get(str(turn_id))
            if position is None:
                position = len(turns)
                index_of[str(turn_id)] = position
                turns.append(
                    {
                        "turn_id": str(turn_id),
                        "conversation_id": str(conversation_id),
                        "turn_sequence": (
                            None if sequence is None else int(sequence)
                        ),
                        "claim_count": 0,
                        "outcomes": [],
                    }
                )
            entry = turns[position]
            entry["claim_count"] += 1
            entry["outcomes"].append(str(outcome))
        return {
            "target_id": target_id,
            "found": bool(turns),
            "active_claim_count": len(rows),
            "turns": turns,
        }


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

        def _send_sse_event(self, payload: dict[str, Any]) -> None:
            """One SSE frame: ``data: <json>\\n\\n`` — the whole event on
            one ``data:`` line (JSON escapes its own newlines, so a frame
            is never split), flushed now: a delta that sits in a buffer is
            not streaming."""

            frame = (
                b"data: "
                + json.dumps(payload, ensure_ascii=False).encode("utf-8")
                + b"\n\n"
            )
            self.wfile.write(frame)
            self.wfile.flush()

        def _run_stream_turn(self, text: str) -> None:
            """A1: the streamed turn — deltas out while the host works.

            The job rides the same one work queue as every host touch (the
            module docstring's one-thread rule); this request thread does
            nothing but drain the turn's queue into SSE delta frames while
            the job runs, then write the one ``final`` frame — exactly one,
            whatever happens: a job the worker never answers within the
            same wait every other face uses still ends with the failure
            shape the blocking turn answers with, and a client that
            disconnects mid-stream stops the *writing*, never the turn (the
            job runs to its durable end; the page's history carries it).
            """

            events: queue.Queue[str] = queue.Queue()
            done = threading.Event()
            box: dict[str, Any] = {}
            failure: list[str] = []

            def job() -> None:
                try:
                    box["payload"] = face.turn_stream(text, events)
                except Exception as exc:  # answered, never swallowed
                    failure.append(f"{type(exc).__name__}: {exc}")
                finally:
                    done.set()

            work.put(job)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            deadline = time.monotonic() + _WORKER_WAIT_SECONDS
            while True:
                drained = False
                while True:
                    try:
                        chunk = events.get_nowait()
                    except queue.Empty:
                        drained = True
                        break
                    try:
                        if isinstance(chunk, str):
                            # A1: a generation increment, as it arrived.
                            self._send_sse_event(
                                {"type": "delta", "text": chunk}
                            )
                        else:
                            # A2: the world's story frame (one dict, the
                            # face already assembled it) — the narrative
                            # order's first beat, before any delta.
                            self._send_sse_event(chunk)
                    except OSError:
                        return  # the reader is gone; the turn runs on
                if done.is_set() and drained:
                    break
                if done.wait(0.02):
                    continue
                if time.monotonic() > deadline:
                    failure.append("the host worker did not answer in time")
                    break
            if failure:
                payload: dict[str, Any] = {
                    "reply": None,
                    "turn_status": None,
                    "failure_reason": failure[0],
                    "teaching_moments": [],
                }
            else:
                payload = box["payload"]
            try:
                self._send_sse_event({"type": "final", **payload})
            except OSError:
                return

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
            elif self.path == "/favicon.ico":
                # The v3-d favicon face: one same-origin answer for the
                # browser's automatic discovery request (a 200 with the
                # inline SVG — never a 404, never an off-site byte).
                body = _FAVICON_SVG.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "image/svg+xml")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path.startswith("/static/"):
                # The static face: the allowlist is the path check — a name
                # outside it (``..``, a subdirectory, a lookalike) answers
                # 404 without touching the filesystem (fail-closed).
                name = self.path[len("/static/"):]
                if name in _STATIC_TYPES:
                    self._send_page_file(name)
                else:
                    self._send_json(404, {"error": "no such page file"})
            elif (
                self.path == "/api/history"
                or self.path.startswith("/api/history?")
            ):
                # The transcript window (the page's load-time recovery
                # read) with the 主线-2 explicit breadth parameters: no
                # query is the unchanged default window; ?full=1 and
                # ?limit=<n> serve more on explicit request. The grammar
                # is fail-closed (an unknown key, a non-1 full value, a
                # non-integer or <1 limit, or both parameters at once are
                # each a 400 人话); the read itself stays on the work
                # queue (the one-thread rule).
                error, full, limit = _history_request(
                    parse_qs(
                        urlsplit(self.path).query, keep_blank_values=True
                    )
                )
                if error is not None:
                    self._send_json(400, {"error": error})
                else:
                    self._run_on_host_thread(
                        lambda: face.history(full=full, limit=limit)
                    )
            elif self.path == "/api/schedule":
                # 主线-2: the review-schedule zone's read — the Scheduler's
                # own classified view (D-INV-009's due decision read where
                # it lives), read-only on the work queue (the diagnostics
                # construction). A host without the scheduler leg answers
                # the honest unavailable shape from the face itself.
                self._run_on_host_thread(face.schedule)
            elif (
                self.path == "/api/target_footprint"
                or self.path.startswith("/api/target_footprint?")
            ):
                # 主线-2: the cross-letter footprint (the 9.12-23④ seam,
                # closed) — one target's ACTIVE learning evidence over the
                # turns that produced it. Grammar: one ?id=<target_id>; a
                # request without it is a bad request; a target with no
                # evidence is the face's own {"found": false} 200 fact.
                id_values = parse_qs(urlsplit(self.path).query).get("id")
                if not id_values or not id_values[0].strip():
                    self._send_json(400, {"error": "need ?id=<target_id>"})
                else:
                    asked = id_values[0].strip()
                    self._run_on_host_thread(
                        lambda: face.target_footprint(asked)
                    )
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
            elif self.path == "/api/settings":
                # 主线-1: the settings section's read — the rollout stage,
                # the §5.1 policy row and the §5.1 disclosure row, one
                # payload, read-only on the work queue (the diagnostics
                # construction). A read failure is a server fact: the
                # route's own 500 posture.
                self._run_on_host_thread(face.settings)
            elif self.path == "/api/world/inbox":
                # W-1-3: the world inbox — the bound world's atomic reveal
                # (the presentation trigger: what a finished run left
                # behind becomes visible the moment the user next looks)
                # plus the whole inbox and the conversation's recent
                # letters, one payload, on the work queue. The face
                # answers its own statuses (404 no binding / 500 a failed
                # reveal — the _run_host_write posture).
                self._run_host_write(face.world_inbox)
            elif self.path == "/api/world/overview":
                # wf-0: the world's one-screen read — name, derived story
                # day, today's revealed notes, the bound resident. A read
                # face on the work queue: it never flips the reveal queue
                # (reading is not opening — the inbox's alone is that
                # trigger), and no binding is the same 404, the same
                # sentence, as the inbox's.
                self._run_host_write(lambda: face.world_overview())
            elif self.path == "/api/world/log":
                # wf-0: the revealed chronicle, grouped by story day,
                # newest first. The red line lives here too: the log
                # never calls reveal_all — a PENDING note is the world's
                # unposted letter, and reading the log never opens it.
                self._run_host_write(lambda: face.world_log())
            elif self.path == "/api/world/residents":
                # wf-0: the cast roster joined to its cards, the current
                # resident marked, letter counts through the history
                # window's own read family. A read face; same 404 guard.
                self._run_host_write(lambda: face.world_residents())
            else:
                self._send_json(404, {"error": "not found"})

        def do_POST(self) -> None:
            if self.path == "/api/turn_stream":
                # A1: the streamed turn. The grammar is the blocking turn's
                # own ({"text": "..."} — a bad body is the same 400 人话,
                # still JSON because nothing has streamed yet); everything
                # after the grammar check rides SSE.
                payload = self._read_json_body()
                text = (
                    payload.get("text") if isinstance(payload, dict) else None
                )
                if not isinstance(text, str) or not text.strip():
                    self._send_json(
                        400, {"error": 'need a JSON body {"text": "..."}'}
                    )
                    return
                self._run_stream_turn(text)
                return
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
            if self.path == "/api/settings/teaching_policy":
                # 主线-1: the eight-knob write. The grammar is validated
                # here, fail-closed (a system column is a 400 人话 naming
                # itself; a word outside the frequency's four is a 400);
                # the store's version discipline rides 200 / 409 from the
                # face (an idempotent replay, a CONFLICT 上浮).
                error, knobs = _settings_knob_request(self._read_json_body())
                if error is not None or knobs is None:
                    self._send_json(400, {"error": error})
                    return
                self._run_host_write(
                    lambda: face.teaching_policy_save(knobs)
                )
                return
            if self.path == "/api/settings/mode":
                # The veto-response cut: the §12 tier write. One word
                # inside the server-declared four, case-sensitive (the
                # enum's own spellings — ``Study-first`` keeps its hyphen);
                # anything else is the 400 below. The face persists the
                # word and swaps the live wiring, so the next turn decides
                # under the new tier; the gate functions are untouched.
                # (The variable is not the frequency route's ``word``: a
                # second same-name assignment in this function would make
                # mypy widen both lambdas' captured types.)
                stage_word = _mode_request_word(self._read_json_body())
                if stage_word is None:
                    self._send_json(400, {"error": _MODE_GRAMMAR})
                    return
                self._run_host_write(lambda: face.mode_save(stage_word))
                return
            if self.path == "/api/settings/ui_language":
                # W-L: the interface language — one whitelisted word
                # (``zh`` / ``en``), persisted; the next inbox read
                # renders in it (the face re-reads the row per request).
                # (The variable is not the frequency route's ``word``: a
                # second same-name assignment in this function would make
                # mypy widen both lambdas' captured types — the mode
                # route's own note.)
                ui_word = _language_request_word(
                    self._read_json_body(),
                    "ui_language",
                    _UI_LANGUAGE_WORDS,
                )
                if ui_word is None:
                    self._send_json(400, {"error": _UI_LANGUAGE_GRAMMAR})
                    return
                self._run_host_write(lambda: face.ui_language_save(ui_word))
                return
            if self.path == "/api/settings/reply_language":
                # W-L: the reply language — one whitelisted word
                # (``zh`` / ``en`` / ``follow``, the compiler's own
                # vocabulary), persisted; the next letter's prompt
                # carries its language row (the coordinator's port
                # re-reads the row per turn, no reassembly).
                reply_word = _language_request_word(
                    self._read_json_body(),
                    "reply_language",
                    RESPONSE_LANGUAGE_WORDS,
                )
                if reply_word is None:
                    self._send_json(400, {"error": _REPLY_LANGUAGE_GRAMMAR})
                    return
                self._run_host_write(
                    lambda: face.reply_language_save(reply_word)
                )
                return
            if self.path == "/api/settings/provider":
                # The provider face (user veto: endpoint/model are
                # page-settable): one or both of base_url / model. The
                # grammar is validated here fail-closed (a non-string, an
                # empty model, a URL without scheme/netloc, or a plaintext
                # non-loopback http destination when the live config has no
                # opt-in is a 400 人话); the face persists the pair and
                # swaps the live provider — the next letter dials the new
                # destination with no restart.
                base_err, base_url, model, api_key = _provider_request_pair(
                    self._read_json_body()
                )
                if base_err is not None:
                    self._send_json(400, {"error": base_err})
                    return
                self._run_host_write(
                    lambda: face.provider_save(base_url, model, api_key)
                )
                return
            if self.path == "/api/settings/provider/profile":
                # 多模型配置档（用户定向）：存/改一个具名配置档（端点 +
                # 模型名 + 可选密钥）；语法在此 fail-closed，写面只落一行
                # 严格 JSON——激活是另一条路（切换才热换）。
                (
                    prof_err,
                    prof_id,
                    prof_name,
                    prof_base,
                    prof_model,
                    prof_key,
                ) = _provider_profile_request(self._read_json_body())
                if prof_err is not None:
                    self._send_json(400, {"error": prof_err})
                    return
                self._run_host_write(
                    lambda: face.provider_profile_save(
                        prof_id, prof_name, prof_base, prof_model, prof_key
                    )
                )
                return
            if self.path == "/api/settings/provider/profile_activate":
                # 多模型配置档：切换 = 应用该档（密钥先落 → 热换 →
                # pair + 指针；下一封信即走新档；重复激活幂等零写）。
                activate_id = _profile_id_request(self._read_json_body())
                if activate_id is None:
                    self._send_json(
                        400,
                        {"error": "请求体须是 {\"id\": 配置档 id}。"},
                    )
                    return
                self._run_host_write(
                    lambda: face.provider_profile_activate(activate_id)
                )
                return
            if self.path == "/api/settings/provider/profile_delete":
                # 多模型配置档：删除（幂等；删现役档不动活配置——指针
                # 归 custom，热换只属于切换面）。
                delete_id = _profile_id_request(self._read_json_body())
                if delete_id is None:
                    self._send_json(
                        400,
                        {"error": "请求体须是 {\"id\": 配置档 id}。"},
                    )
                    return
                self._run_host_write(
                    lambda: face.provider_profile_delete(delete_id)
                )
                return
            if self.path == "/api/settings/disclosure":
                # fr-A: the disclosure rule-set write — the full new set,
                # versioned like the policy writes. The grammar is
                # validated here, fail-closed (a duplicate persona rule, an
                # out-of-vocabulary level or an unknown key is a 400 人话
                # naming itself); the store's version discipline rides
                # 200 / 409 from the face.
                self._run_host_write(
                    lambda: face.disclosure_save(self._read_json_body())
                )
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

    # W-1-3: the web conversation lives in the builtin world — the binding
    # (and its cast signature) written here, idempotently, so the inbox
    # route and the turn wiring have their referent on every fresh start.
    # The world is the first builtin package in file-name order (one
    # builtin ships today; the multi-world choice is a later cut's), the
    # actor is that package's first cast member through the loader's own
    # derivation (single source — never a second id law), and the binding
    # id derives from the conversation so a replay is the store's
    # idempotent no-op. A refusal — a conversation already bound to a
    # different world, a store without the world leg — is said out loud
    # and the serving goes on: the same failure-tolerant posture the
    # recovery lines hold, and the inbox answers its honest 404 for as
    # long as the binding is absent.
    world_store = getattr(host, "world_store", None)
    if world_store is not None:
        builtin = None
        try:
            for package_path in sorted(BUILTIN_WORLDS_DIR.glob("*.json")):
                loaded_world = load_world_package(package_path)
                if isinstance(loaded_world, Ok):
                    builtin = loaded_world.value
                    break
        except OSError:
            builtin = None
        if builtin is not None and builtin.cast:
            bound = world_store.bind_conversation(
                f"bind-{conversation}",
                builtin.world_id,
                _actor_id_for(builtin.world_id, builtin.cast[0].name),
                conversation,
                datetime.now(tz=UTC).isoformat(),
            )
            if isinstance(bound, Err):
                print(
                    "elc web: world binding unavailable:"
                    f" {bound.error.code.value}: {bound.error.message}",
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
