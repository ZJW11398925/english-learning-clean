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
import sys
import threading
import uuid
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Sequence, TextIO

from elc.cli import (
    RUNTIME_VERSION,
    ObservationSection,
    observation_drift_count,
    observation_sections,
)
from elc.cli import main as cli_main
from elc.conversation.types import CommitUserTurn
from elc.host import Host
from elc.persona.provider import PersonaProvider
from elc.platform.types import (
    ClientMessageId,
    ConversationId,
    Err,
    InputId,
    InteractionChannel,
)
from elc.runtime.controller import TeachingReplyRequest
from elc.runtime.types import InputEnvelope
from elc.teaching.envelope import (
    AttemptPayload,
    TeachingControlIntent,
    TeachingResponseEnvelope,
)
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
    word = str(outcome)
    return f"{word}（{_OUTCOME_CN.get(word, word)}）"


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


_PAGE = """<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>英语客厅 · Study-first dogfood</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 46rem; margin: 2rem auto;
         padding: 0 1rem; color: #222; }
  h1 { font-size: 1.3rem; } h2 { font-size: 1.05rem; margin-top: 2rem; }
  #messages { border: 1px solid #ccc; border-radius: 6px; min-height: 14rem;
              padding: .75rem; display: flex; flex-direction: column; gap: .5rem; }
  .user { align-self: flex-end; background: #e8f0fe; padding: .4rem .7rem;
          border-radius: 10px 10px 2px 10px; max-width: 80%; white-space: pre-wrap; }
  .assistant { align-self: flex-start; background: #f1f1f1; padding: .4rem .7rem;
               border-radius: 10px 10px 10px 2px; max-width: 80%;
               white-space: pre-wrap; }
  .failure { align-self: flex-start; background: #fde8e8; color: #8a1f1f;
             padding: .4rem .7rem; border-radius: 6px; max-width: 80%;
             font-family: monospace; font-size: .85rem; }
  form { display: flex; gap: .5rem; margin-top: .75rem; }
  #text { flex: 1; padding: .45rem; }
  .moment { border: 1px solid #b8c9b8; background: #f2f8f2; border-radius: 6px;
            padding: .5rem .75rem; margin-top: .5rem; }
  .moment b { color: #2c5a2c; }
  .moment.skipped { border-color: #bbb; background: #f4f4f4; opacity: .55; }
  .moment.skipped b { color: #777; }
  .moment button { margin-top: .35rem; font-size: .85rem; }
  .replyrow { display: flex; gap: .4rem; margin-top: .35rem; }
  .replytext { flex: 1; padding: .3rem; min-width: 0; font-size: .85rem; }
  .system { align-self: center; color: #666; font-size: .85rem; }
  button { padding: .45rem .9rem; cursor: pointer; }
  pre { background: #f7f7f7; border: 1px solid #ddd; border-radius: 6px;
        padding: .75rem; overflow-x: auto; }
  .note { color: #666; font-size: .85rem; }
</style>
</head>
<body>
<h1>英语客厅 · Study-first dogfood</h1>
<p class="note">本地单用户页面（127.0.0.1，无鉴权）——你说英语，客厅用英语回你；
若这一轮触发了自动教学，教学时刻卡会出现在下方。</p>
<section>
  <h2>对话</h2>
  <div id="messages"></div>
  <form id="send">
    <input id="text" autocomplete="off" placeholder="用英语说点什么……">
    <button type="submit">发送</button>
  </form>
</section>
<section>
  <h2>教学时刻（本轮）</h2>
  <div id="moments"><p class="note">发送一轮后显示本轮打开的教学时刻。</p></div>
</section>
<section>
  <h2>观察读数</h2>
  <button id="obs" type="button">拉取观察读数</button>
  <pre id="obsout" hidden></pre>
</section>
<script>
"use strict";
const messages = document.getElementById("messages");
const momentsBox = document.getElementById("moments");

function addLine(cls, text) {
  const div = document.createElement("div");
  div.className = cls;
  div.textContent = text;            // textContent, never innerHTML: the
  messages.appendChild(div);          // user's own words stay inert text
  messages.scrollTop = messages.scrollHeight;
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
    card.className = "moment";
    const b = document.createElement("b");
    if (m.title) {
      b.textContent = "💡 教学时刻：" + m.title;
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
  submit.textContent = "提交作答";
  submit.addEventListener("click", () => submitAttempt(card, input));
  const skip = document.createElement("button");
  skip.type = "button";
  skip.textContent = "跳过教学";
  skip.addEventListener("click", () => skipMoment(card));
  row.appendChild(input);
  row.appendChild(submit);
  row.appendChild(skip);
  card.appendChild(row);
}

function disarmMomentCard(card) {
  for (const row of Array.from(card.querySelectorAll(".replyrow"))) {
    row.remove();
  }
}

function readReplyAnswer(card, data) {
  // the reply result's own words, never a fabricated one: the new state
  // plus the feedback verdict when the reply carried one
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
    card.appendChild(document.createElement("br"));
    card.appendChild(document.createTextNode("判分反馈：" + data.feedback));
  }
  if (data.moment_state === "AWAITING_USER") {
    // the moment lives on (a miss re-prompts): the user can retry or skip
    addReplyControls(card);
  } else {
    card.classList.add("skipped");
  }
}

async function submitAttempt(card, input) {
  const text = input.value.trim();
  if (!text) return;
  const res = await fetch("/api/teaching_reply", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ control: "attempt", text: text }),
  });
  const data = await res.json();
  if (res.status !== 200) {
    addLine("failure", data.error || "提交作答失败");
    return;
  }
  if (data.accepted) {
    addLine("system", "已提交作答");
    readReplyAnswer(card, data);
  } else {
    addLine("failure", data.error || "无法提交这个作答");
  }
}

async function skipMoment(card) {
  const res = await fetch("/api/teaching_reply", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ control: "skip" }),
  });
  const data = await res.json();
  if (res.status !== 200) {
    addLine("failure", data.error || "跳过教学失败");
    return;
  }
  if (data.accepted) {
    disarmMomentCard(card);
    card.classList.add("skipped");
    card.appendChild(document.createTextNode(" · 已跳过"));
    addLine("system", "教学已跳过");
  } else {
    addLine("failure", data.error || "无法跳过这个教学时刻");
  }
}

async function postTurn(text) {
  addLine("user", text);
  const res = await fetch("/api/turn", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: text }),
  });
  const data = await res.json();
  if (data.reply !== null && data.reply !== undefined) {
    addLine("assistant", data.reply);
  } else if (data.turn_status !== null && data.turn_status !== undefined) {
    addLine("failure", "[" + data.turn_status + "] " +
      (data.failure_reason || "无回复"));
  } else if (data.failure_reason) {
    addLine("failure", data.failure_reason);
  }
  showMoments(data.teaching_moments || []);
}

document.getElementById("send").addEventListener("submit", (event) => {
  event.preventDefault();
  const input = document.getElementById("text");
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  postTurn(text);
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

window.addEventListener("DOMContentLoaded", loadHistory);
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

    def current_teaching(self) -> dict[str, Any]:
        """The conversation's open teaching moment, for the page's reload.

        The card a turn response rendered disappears on refresh, yet the
        moment it showed may still be open and still hold the lock — losing
        the card loses the only reply entry points (attempt box, skip
        button). This answers that same moment in the same shape the turn
        response served it (human fields included), or ``{"moment": None}``
        when nothing is open — the page rebuilds the card either way, so a
        refresh can never strand an open teaching without its controls.
        """

        row = self._host.db.execute(
            "SELECT m.focus_target, m.lifecycle_state, m.target_mode"
            " FROM active_teaching_lock l"
            " JOIN teaching_moment m ON m.moment_id = l.moment_id"
            " WHERE l.conversation_id = ?",
            (str(self._conversation_id),),
        ).fetchone()
        if row is None or str(row[1]) != MomentState.AWAITING_USER.value:
            return {"moment": None}
        focus_id = _focus_id_of(str(row[0]))
        state = str(row[1])
        kind = str(row[2])
        return {
            "moment": {
                "focus_target_id": focus_id,
                "lifecycle_state": state,
                "kind": kind,
                "title": self._moment_title(focus_id),
                "status_cn": _STATUS_CN.get(state, state),
                "kind_cn": _KIND_CN.get(kind, kind),
            }
        }

    def teaching_reply(
        self, control: str, text: str | None = None
    ) -> dict[str, Any]:
        """One user reply to the open teaching moment — skip or attempt.

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
          holding the lock, so the card can ask again).

        An ``Err`` from the entry is a runtime fact — 200, ``accepted:
        false``, the error sentence; the face never fabricates a state,
        the reported ``moment_state`` is the reply result's own word (and
        stays consistent with the durable row the next read sees).
        ``feedback`` is the result's own evaluation verdict, readable, or
        ``None`` when the reply carried no evaluation — never a
        fabricated judgement.
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
        else:
            envelope = TeachingResponseEnvelope(
                control_intent=TeachingControlIntent.SKIP, attempt_present=False
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
        return {
            "accepted": True,
            "moment_state": result.value.moment_state.value,
            "error": None,
            "feedback": _feedback_of(result.value),
        }

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
                self._run_on_host_thread(face.current_teaching)
            elif self.path == "/api/observations":
                self._run_on_host_thread(face.observations)
            else:
                self._send_json(404, {"error": "not found"})

        def do_POST(self) -> None:
            if self.path not in ("/api/turn", "/api/teaching_reply"):
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
                # The reply grammar is exactly {"control": "skip"} or
                # {"control": "attempt", "text": "..."} — any other body
                # (no JSON, another key, an unknown control word, an
                # attempt without a non-empty text) is a bad request, not
                # a runtime fact.
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
                self._send_json(
                    400,
                    {
                        "error": (
                            'need a JSON body {"control": "skip"} or'
                            ' {"control": "attempt", "text": "..."}'
                        )
                    },
                )
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
