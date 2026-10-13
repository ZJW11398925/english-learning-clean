"""V3-8e — the minimal reading face: the real egress adapter, the routes,
the render acknowledgement and the durable-position law
(TASK-OPI-cddb517c-…33 / the opening ruling ``DEC-OPI-cddb517c-…31``).

**What this suite proves, stated honestly.** The reading face serves the
Gold Scenario through the **real** chain — ``elc.web``'s routes →
``elc.narrative_web``'s service half → the V3-8c providers over the
V3-8e egress adapter → the persona package's ``OpenAICompatibleProvider``
→ an **injected** transport that answers the Gold Scenario's scripted
payloads. No socket is opened and no real credential is read (the
transport is a callable and the secret source is a test double); the
driver is the scripted completion, so the prose is structural evidence —
the user's 「好玩」 acceptance with a real model stays V3-8e's own manual
run.

Pinned here:

1. the egress adapter (2a) — ``ProviderOutput.text`` in / ``error`` out,
   values never raises, the prompt and the key never carried back, the
   unconfigured and non-OpenAI faces answering honest codes;
2. the routes (2b) — ``start`` (idempotent, zero-write replay), the
   durable ``state``, ``continue`` (one segment per call, the gate opened
   at its beat), ``submit`` (the user's own free input → the ruling →
   the continuation with its ``outcome_ref`` → the gate CLOSED → the
   auto-routed CHAPTER replan), ``settle``, ``next_chapter`` and ``ack``
   (``reader_exposure`` rows and nothing else);
3. the durable-position law — a restart over the same app.db continues
   exactly where the story stands, and a crashed ruling is finished from
   the stored submission with **no second ruling and no re-generated
   prose** (the replay providers);
4. the poll posture — ``/api/v3/state`` answers while a drive holds the
   work queue (the ``/api/teaching/current`` exception);
5. the honest faces — an unconfigured endpoint, a non-OpenAI provider, a
   host without the V3 legs, and the fail-closed route grammars;
6. the page half — the new file set served over the static allowlist,
   zero external resources, and the main UI untouched (no entry, no
   reference).
"""

from __future__ import annotations

import contextlib
import json
import os
import socket
import sqlite3
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping

from elc.host import open_host
from elc.narrative_web import (
    READER_ID,
    REASON_NO_EGRESS,
    NarrativeWebFace,
    PersonaEgressCompletion,
    narrative_state_ro,
)
from elc.persona.openai_provider import (
    REASON_NOT_CONFIGURED,
    OpenAICompatibleConfig,
    OpenAICompatibleProvider,
)
from elc.persona.provider import ScriptedPersonaProvider
from elc.persona.types import ProviderOutput
from elc.platform.db.epoch import open_runtime_epoch
from elc.platform.db.migrations import apply_migrations
from elc.platform.types import SecretRef
from elc.web import run_web
from elc.world import gold
from elc.world.action import ActionStatus, GateStatus, action_of, get_gate
from elc.world.bible import SqliteBibleStore
from elc.world.cast import SqliteCastStore
from elc.world.narrative import SqliteNarrativeStore
from elc.world.store import SqliteWorldStore
from tests.host.support import FixedSecret, RecordingPost, config

REPO = Path(__file__).resolve().parents[2]
WEBUI = REPO / "src" / "elc" / "webui"

#: The loopback opener (the W-1 suite's own): an empty proxy map, so a
#: developer's proxy can never stand between the test and the page.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

#: The route-level submission id this suite mints. It is the **fixture's
#: own anchor** on purpose: the Gold Scenario's scripted completion keys
#: its CHAPTER-replan payload on ``rp:<gate>:<submission_id>`` (the
#: fixture's documented keying law — a real model never reads the id),
#: so the scripted drive must carry the fixture's id. The user's own
#: part is the free ``intent_text``, which is what the resolver's
#: scripted answer keys on.
WEB_SUBMISSION_ID = gold.SUBMISSION_ID

_NOW = "2026-10-13T00:00:00+00:00"
_LATER = "2026-10-13T01:00:00+00:00"

_ARM_OPENINGS = (
    ("writer", "You are the POV writer"),
    ("planner", "You are the scene planner"),
    ("director", "You are the world director"),
    ("resolver", "You are the action resolver"),
)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _arm_of(prompt: str) -> str:
    head = prompt[:200]
    for arm, opening in _ARM_OPENINGS:
        if opening in head:
            return arm
    return "unknown"


class _GoldPost:
    """The offline ``HttpPost``: answers the Gold Scenario's scripted
    payloads, one OpenAI-shaped 2xx body per prompt — and records every
    call (arm-labelled), which is what the model-call pins read.

    ``release`` turns the first writer call into a blocking one (the poll
    pin): the transport sets ``blocked`` and waits for ``release`` — no
    sleep anywhere, the test decides when the drive may finish.
    """

    def __init__(self, release: threading.Event | None = None) -> None:
        self.script = gold.gold_completion()
        self.calls: list[tuple[str, str]] = []
        self.blocked = threading.Event()
        self.release = release
        self._blocked_once = False

    def __call__(
        self,
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout: float,
    ) -> tuple[int, bytes]:
        document = json.loads(body.decode("utf-8"))
        prompt = document["messages"][0]["content"]
        arm = _arm_of(prompt)
        self.calls.append((arm, prompt))
        if (
            arm == "writer"
            and self.release is not None
            and not self._blocked_once
        ):
            self._blocked_once = True
            self.blocked.set()
            self.release.wait(timeout=30.0)
        outcome = self.script.complete(prompt)
        text = "" if outcome.text is None else outcome.text
        reply = json.dumps({"choices": [{"message": {"content": text}}]})
        return 200, reply.encode("utf-8")

    def prompts(self, arm: str) -> list[str]:
        return [prompt for name, prompt in self.calls if name == arm]


def _gold_egress(post: _GoldPost) -> OpenAICompatibleProvider:
    """The real persona adapter over the offline transport (a test
    double's key: no real credential is read anywhere in this suite)."""

    return OpenAICompatibleProvider(
        OpenAICompatibleConfig(
            base_url="https://egress.invalid/v1",
            model="scripted-model",
            secret_ref=SecretRef("test-key-ref"),
        ),
        FixedSecret(value="sk-offline-sentinel-NEVER-LEAK"),
        transport=post,
    )


def _get_json(port: int, path: str) -> tuple[int, Any]:
    with _OPENER.open(
        f"http://127.0.0.1:{port}{path}", timeout=30
    ) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def _post_json(port: int, path: str, payload: Any) -> tuple[int, Any]:
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return _open_request(request)


def _post_empty(port: int, path: str) -> tuple[int, Any]:
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", data=b"", method="POST"
    )
    return _open_request(request)


def _open_request(request: urllib.request.Request) -> tuple[int, Any]:
    try:
        with _OPENER.open(request, timeout=30) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


@dataclass
class _V3Stack:
    """One serving stack over the reading face: the port to hit, the
    transport's log and the stop switch."""

    port: int
    stop: threading.Event
    thread: threading.Thread
    post: _GoldPost

    def state(self) -> dict[str, Any]:
        status, payload = _get_json(self.port, "/api/v3/state")
        assert status == 200
        return payload

    def start(self) -> dict[str, Any]:
        return _post_empty(self.port, "/api/v3/start")[1]

    def advance(
        self, end_scene: bool = False
    ) -> tuple[int, dict[str, Any]]:
        return _post_json(
            self.port, "/api/v3/continue", {"end_scene": end_scene}
        )

    def submit(self, body: Any) -> tuple[int, dict[str, Any]]:
        return _post_json(self.port, "/api/v3/submit", body)

    def ack(self, passage_ids: list[str]) -> tuple[int, dict[str, Any]]:
        return _post_json(
            self.port, "/api/v3/ack", {"passage_ids": passage_ids}
        )


@contextlib.contextmanager
def v3_stack(
    app_db: Path, *, provider: Any = None, post: _GoldPost | None = None
) -> Iterator[_V3Stack]:
    """Serve the real ``run_web`` over one host (the W-1 suite's worker
    shape): the host's whole lifecycle lives on the worker thread — the
    one thread the work loop runs host touches on."""

    port = _free_port()
    ready = threading.Event()
    stop = threading.Event()
    box: dict[str, Any] = {}
    transport = post if post is not None else _GoldPost()
    live = provider if provider is not None else _gold_egress(transport)

    def worker() -> None:
        try:
            host = open_host(app_db, provider=live)
            box["host"] = host
            run_web(
                host,
                port,
                conversation="web-v3",
                ready=ready,
                stop=stop,
            )
        except BaseException as exc:  # surfaced to the test thread below
            box["error"] = exc
            ready.set()

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    try:
        assert ready.wait(timeout=60.0), "the web worker never became ready"
        if "error" in box:
            raise box["error"]
        yield _V3Stack(port=port, stop=stop, thread=thread, post=transport)
    finally:
        stop.set()
        thread.join(timeout=60.0)
        assert not thread.is_alive(), "the web worker did not stop"


# -- the durable reads this suite's assertions make -------------------------


def _read(app_db: Path, sql: str, params: tuple[Any, ...] = ()) -> Any:
    connection = sqlite3.connect(app_db)
    try:
        return connection.execute(sql, params).fetchone()
    finally:
        connection.close()


def _count(app_db: Path, table: str) -> int:
    row = _read(app_db, f"SELECT COUNT(*) FROM {table}")  # noqa: S608
    return int(row[0])


def _one(app_db: Path, table: str, column: str) -> Any:
    row = _read(app_db, f"SELECT {column} FROM {table}")  # noqa: S608
    return None if row is None else row[0]


# ---------------------------------------------------------------------------
# 1. the egress adapter (2a)
# ---------------------------------------------------------------------------


def _completion_body(text: str) -> bytes:
    return json.dumps({"choices": [{"message": {"content": text}}]}).encode(
        "utf-8"
    )


def test_the_egress_adapter_maps_text_in_and_values_out() -> None:
    """A surfaced answer becomes ``CompletionOutcome(text=…)``; a
    transport failure, an HTTP status and a missing coordinate each
    become a short ``error`` code — never a raise, never a fabricated
    text."""

    post = RecordingPost(status=200, payload=_completion_body("a segment"))
    provider = OpenAICompatibleProvider(
        config(), FixedSecret(), transport=post
    )
    outcome = PersonaEgressCompletion(lambda: provider).complete("PROMPT-A")
    assert outcome.text == "a segment"
    assert outcome.error is None
    assert str(post.calls[0]["url"]).endswith("/chat/completions")

    slow = PersonaEgressCompletion(
        lambda: OpenAICompatibleProvider(
            config(),
            FixedSecret(),
            transport=RecordingPost(raises=TimeoutError("slow")),
        )
    ).complete("PROMPT-B")
    assert slow.text is None
    assert slow.error == "timeout"

    refused = PersonaEgressCompletion(
        lambda: OpenAICompatibleProvider(
            config(), FixedSecret(), transport=RecordingPost(status=500)
        )
    ).complete("PROMPT-C")
    assert refused.text is None
    assert refused.error == "http-500"

    bare = OpenAICompatibleProvider(
        OpenAICompatibleConfig(
            base_url="", model="", secret_ref=SecretRef("api-key")
        ),
        FixedSecret(),
        transport=RecordingPost(status=200, payload=b"{}"),
    )
    unconfigured = PersonaEgressCompletion(lambda: bare).complete("PROMPT-D")
    assert unconfigured.text is None
    assert unconfigured.error == REASON_NOT_CONFIGURED


def test_the_egress_adapter_never_carries_the_prompt_or_the_key() -> None:
    """The value semantics' honesty half: a failure value is a code —
    the prompt never rides back, and a 2xx answer that echoes the key is
    refused as ``key-echo`` (the persona adapter's guard, upstream of
    this seam)."""

    key = "sk-offline-sentinel-NEVER-LEAK"
    unknown = PersonaEgressCompletion(lambda: None).complete("PROMPT-E")
    assert unknown.error == REASON_NO_EGRESS
    assert "PROMPT-E" not in str(unknown)

    scripted = ScriptedPersonaProvider(script=(ProviderOutput(text="x"),))
    not_openai = PersonaEgressCompletion(lambda: scripted).complete(
        "PROMPT-F"
    )
    assert not_openai.error == REASON_NO_EGRESS
    assert "PROMPT-F" not in str(not_openai)

    echo = PersonaEgressCompletion(
        lambda: OpenAICompatibleProvider(
            config(),
            FixedSecret(value=key),
            transport=RecordingPost(
                status=200, payload=_completion_body("see " + key)
            ),
        )
    ).complete("PROMPT-G")
    assert echo.text is None
    assert echo.error == "key-echo"
    assert key not in str(echo)
    assert "PROMPT-G" not in str(echo)


# ---------------------------------------------------------------------------
# 2. the routes (2b) — the Gold drive over the scripted egress
# ---------------------------------------------------------------------------


def _to_the_gate(stack: _V3Stack) -> None:
    """start → two segments → the gate opened (the shared approach every
    route test below uses)."""

    started = stack.start()
    assert started["ok"] is True, started["error"]
    for _ in range(2):
        driven = stack.advance()[1]
        assert driven["ok"] is True, driven["error"]
    opened = stack.advance()[1]
    assert opened["ok"] is True, opened["error"]
    assert opened["did"]["kind"] == "gate_open"


def test_start_is_idempotent_and_the_state_carries_the_durable_faces(
    tmp_path: Path,
) -> None:
    """``start`` seeds the world and plans the first chapter; a replay is
    a zero-write no-op (the library faces' own idempotency). ``state``
    answers the whole durable read in one payload."""

    app_db = tmp_path / "app.db"
    with v3_stack(app_db) as stack:
        started = stack.start()
        assert started["ok"] is True, started["error"]
        assert started["world"]["exists"] is True
        assert started["world"]["name"] == gold.WORLD_NAME
        assert started["chapter"]["chapter_index"] == 1
        assert started["chapter"]["status"] == "PLANNED"
        assert started["plan"]["plan_revision"] == 1
        assert started["plan"]["scene_count"] == 4
        assert [row["scene_id"] for row in started["roster"]] == [
            gold.S1,
            gold.S2,
            gold.S3,
            gold.S4,
        ]
        # S1–S3 are the author's scripted scenes; S4 carries no scripted
        # beats (the replan retires it) — an open scene until then.
        assert [row["anchored"] for row in started["roster"]] == [
            True,
            True,
            True,
            False,
        ]
        assert started["next"]["kind"] == "segment"
        assert started["controls"]["can_continue"] is True
        assert started["controls"]["can_settle"] is False
        assert started["passages"] == []
        assert started["gates"] == []

        # the replay: same shape, zero writes.
        snapshot = {
            table: _count(app_db, table)
            for table in (
                "world",
                "world_actor",
                "world_player_character",
                "world_bible_revision",
                "world_chapter",
                "world_chapter_plan",
                "world_scene",
                "segment_commit",
            )
        }
        replayed = stack.start()
        assert replayed["ok"] is True
        assert replayed["chapter"] == started["chapter"]
        assert {table: _count(app_db, table) for table in snapshot} == (
            snapshot
        )
        # the chapter planning arm ran exactly once (the director).
        assert len(stack.post.prompts("director")) == 1


def test_continue_writes_one_segment_per_call_and_opens_the_gate(
    tmp_path: Path,
) -> None:
    """One continue = one segment (the position from ``segment_commit``);
    reaching the gate beat opens the durable gate and stops there — the
    OPEN row is the story's stop, the options are the author's."""

    app_db = tmp_path / "app.db"
    with v3_stack(app_db) as stack:
        started = stack.start()
        assert started["world"]["current_tick"] == 0

        first = stack.advance()[1]
        assert first["did"] == {
            "kind": "segment",
            "scene_id": gold.S1,
            "passage_ids": [f"{gold.S1}-p0001"],
        }
        assert [row["passage_id"] for row in first["passages"]] == [
            f"{gold.S1}-p0001"
        ]
        assert first["world"]["current_tick"] == 300
        assert first["scene"]["status"] == "ACTIVE"
        assert first["scene"]["pov_actor_id"] == gold.LIA

        second = stack.advance()[1]
        assert [row["passage_id"] for row in second["passages"]] == [
            f"{gold.S1}-p0001",
            f"{gold.S1}-p0002",
        ]
        assert second["world"]["current_tick"] == 540
        assert second["next"]["kind"] == "gate"

        opened = stack.advance()[1]
        assert opened["did"] == {
            "kind": "gate_open",
            "gate_id": gold.GATE,
        }
        connection = sqlite3.connect(app_db)
        try:
            gate_row = get_gate(connection, gold.GATE)
        finally:
            connection.close()
        assert gate_row is not None
        assert gate_row.status is GateStatus.OPEN
        assert gate_row.options == gold.GATE_OPTIONS
        assert opened["gates"] == [
            {
                "gate_id": gold.GATE,
                "scene_id": gold.S1,
                "status": "OPEN",
                "opened_at_tick": 540,
                "options": list(gold.GATE_OPTIONS),
                "submission_id": None,
                "intent_text": None,
            }
        ]
        assert opened["controls"]["can_submit"] is True
        # the gate open is not a segment: the passage count stands.
        assert len(opened["passages"]) == 2
        # one real writing per segment — never a re-generation.
        assert len(stack.post.prompts("writer")) == 2


def test_submit_lands_the_free_input_the_ruling_and_the_continuation(
    tmp_path: Path,
) -> None:
    """The user's own free input goes in; the ruling lands (NCP-2), the
    continuation passage carries its ``outcome_ref``, the gate closes,
    and the CHAPTER verdict auto-routes the replan (revision 2, the
    discarded scene gone from the roster)."""

    app_db = tmp_path / "app.db"
    with v3_stack(app_db) as stack:
        _to_the_gate(stack)
        status, payload = stack.submit(
            {
                "submission_id": WEB_SUBMISSION_ID,
                "intent_text": gold.GOLD_INTENT,
            }
        )
        assert status == 200
        assert payload["ok"] is True, payload["error"]
        assert payload["did"]["gate_id"] == gold.GATE
        assert payload["did"]["closed_gates"] == [gold.GATE]
        assert payload["did"]["passage_ids"] == [f"{gold.S1}-p0003"]
        assert payload["gates"] == []

        connection = sqlite3.connect(app_db)
        try:
            action = action_of(connection, gold.GATE)
        finally:
            connection.close()
        assert action is not None
        assert action.status is ActionStatus.COMMITTED
        assert action.intent_text == gold.GOLD_INTENT
        assert action.replan_scope is not None
        assert action.replan_scope.value == "CHAPTER"
        # the continuation carries the ruling; the gate is closed.
        assert _read(
            app_db,
            "SELECT outcome_ref FROM narrative_passage WHERE passage_id = ?",
            (f"{gold.S1}-p0003",),
        ) == (gold.ACTION_ID,)
        assert _read(
            app_db,
            "SELECT status FROM user_gate WHERE gate_id = ?",
            (gold.GATE,),
        ) == ("CLOSED",)
        # the CHAPTER replan landed as revision 2; the discarded scene is
        # gone from the roster and from the adopted plan.
        assert payload["plan"]["plan_revision"] == 2
        assert _read(
            app_db,
            "SELECT chapter_plan_id FROM world_chapter_plan WHERE"
            " chapter_id = ? AND status = 'ADOPTED'",
            (gold.CH1,),
        ) == (gold.PLAN_R2,)
        assert [row["scene_id"] for row in payload["roster"]] == [
            gold.S2,
            gold.S3,
        ]
        assert payload["scene"]["scene_id"] == gold.S2
        # exactly one ruling was made (the resolver was asked once).
        assert len(stack.post.prompts("resolver")) == 1

        # a second submit has nothing to drive — an honest sentence.
        again = stack.submit({})
        assert again[1]["ok"] is False
        assert "没有等你提交的门" in again[1]["error"]


def test_settle_and_next_chapter_close_and_reopen_the_story(
    tmp_path: Path,
) -> None:
    """The re-planned scenes are walked out (one segment per call), the
    chapter settles (``ACTIVE → SETTLING → CLOSED`` + NCP-4), and the
    next chapter is planned through the real Director provider — its
    scenes are fresh (not the fixture's anchors)."""

    app_db = tmp_path / "app.db"
    with v3_stack(app_db) as stack:
        _to_the_gate(stack)
        landed = stack.submit(
            {
                "submission_id": WEB_SUBMISSION_ID,
                "intent_text": gold.GOLD_INTENT,
            }
        )[1]
        assert landed["ok"] is True, landed["error"]
        # S2 (two segments) and S3 (one) — three more continues.
        for expected in (4, 5, 6):
            driven = stack.advance()[1]
            assert driven["ok"] is True, driven["error"]
            assert len(driven["passages"]) == expected
        walked = stack.state()
        assert walked["controls"]["can_settle"] is True
        assert walked["next"]["kind"] == "settle"

        settled = _post_empty(stack.port, "/api/v3/settle")[1]
        assert settled["ok"] is True, settled["error"]
        assert settled["chapter"]["status"] == "CLOSED"
        assert settled["settlement"]["chapter_id"] == gold.CH1
        assert "sg:" in settled["settlement"]["summary"]
        assert settled["next"]["kind"] == "next_chapter"
        assert settled["controls"]["can_next_chapter"] is True
        # settle again is the idempotent replay.
        assert _post_empty(stack.port, "/api/v3/settle")[1]["ok"] is True

        nexted = _post_empty(stack.port, "/api/v3/next_chapter")[1]
        assert nexted["ok"] is True, nexted["error"]
        assert nexted["chapter"]["chapter_index"] == 2
        assert nexted["chapter"]["status"] == "PLANNED"
        assert nexted["plan"]["plan_revision"] == 1
        assert nexted["plan"]["scene_count"] == 2
        assert nexted["settlement"] is None  # the new chapter has none
        assert nexted["roster"]
        assert all(row["anchored"] is False for row in nexted["roster"])
        # the Director's second draft saw the first chapter's settlement
        # (the replan arm is the same provider face — filtered out here).
        drafts = [
            prompt
            for prompt in stack.post.prompts("director")
            if "The replan's own faces:" not in prompt
        ]
        assert len(drafts) == 2
        assert gold.CH1 in drafts[1]
        assert gold.S1_PROSE_1 in drafts[1]
        # the chapter-2 scenes' prose is outside the scripted screenplay
        # (the fixture's own key law) — the drive answers the honest
        # provider-failure sentence and lands no passage: a refusal is a
        # 200 payload fact, never a 500, and the retry stays available.
        before = len(stack.state()["passages"])
        failed = stack.advance()[1]
        assert failed["ok"] is False
        assert "这一次写作没有完成（transport-error）" in failed["error"]
        assert len(failed["passages"]) == before


def test_ack_records_exposure_only(tmp_path: Path) -> None:
    """``/api/v3/ack`` writes ``reader_exposure`` rows for what the page
    rendered — idempotently, and nothing else: no actor memory, no
    belief (N-INV-005's seal), no commit-row movement."""

    app_db = tmp_path / "app.db"
    with v3_stack(app_db) as stack:
        stack.start()
        driven = stack.advance()[1]
        ids = [row["passage_id"] for row in driven["passages"]]
        before = {
            table: _count(app_db, table)
            for table in (
                "reader_exposure",
                "actor_memory",
                "narrative_passage",
                "segment_commit",
            )
        }
        status, acked = stack.ack(ids)
        assert status == 200
        assert acked == {
            "ok": True,
            "reader_id": READER_ID,
            "recorded": ids,
            "missed": [],
        }
        assert _count(app_db, "reader_exposure") == (
            before["reader_exposure"] + 1
        )
        assert _read(
            app_db,
            "SELECT reader_id FROM reader_exposure WHERE passage_id = ?",
            (ids[0],),
        ) == (READER_ID,)
        # the replay is the first-wins no-op.
        stack.ack(ids)
        assert _count(app_db, "reader_exposure") == (
            before["reader_exposure"] + 1
        )
        # nothing else moved — the record face is decoupled.
        for table in ("actor_memory", "narrative_passage", "segment_commit"):
            assert _count(app_db, table) == before[table], table
        # a dangling id is the honest miss (its own FK), not a crash.
        status, missed = stack.ack(["no-such-passage"])
        assert status == 200
        assert missed["ok"] is False
        assert missed["missed"][0]["passage_id"] == "no-such-passage"


# ---------------------------------------------------------------------------
# 3. the durable-position law
# ---------------------------------------------------------------------------


def test_the_position_survives_a_restart(tmp_path: Path) -> None:
    """Two segments in, the process stops; a fresh stack over the same
    app.db reads the same position from the rows and continues exactly
    where the story stood — no in-process state anywhere."""

    app_db = tmp_path / "app.db"
    with v3_stack(app_db) as first:
        first.start()
        first.advance()
        second = first.advance()[1]
        assert len(second["passages"]) == 2
    with v3_stack(app_db) as resumed:
        state = resumed.state()
        assert state["world"]["current_tick"] == 540
        assert [row["passage_id"] for row in state["passages"]] == [
            f"{gold.S1}-p0001",
            f"{gold.S1}-p0002",
        ]
        assert state["next"]["kind"] == "gate"
        opened = resumed.advance()[1]
        assert opened["did"]["kind"] == "gate_open"
        # the prefix was re-presented to the orchestrator (the script law)
        # but the model was asked for nothing: the replay providers
        # answered the committed segments from canon — zero writer calls.
        assert resumed.post.prompts("writer") == []


def test_a_crashed_ruling_finishes_from_canon_alone(tmp_path: Path) -> None:
    """The HARD GATE's window, read by the face: a gate COMMITTED with
    no continuation (the fixture's own pipeline drives up to the gate —
    the crash stand-in). ``submit`` with an empty body re-drives it from
    the stored submission: the ruling is replayed from canon (no second
    resolver call), the continuation is the only fresh writing, and the
    gate closes in that same commit."""

    app_db = tmp_path / "app.db"
    connection = sqlite3.connect(app_db)
    connection.execute("PRAGMA foreign_keys=ON")
    apply_migrations(connection)
    fence = open_runtime_epoch(connection)
    worlds = SqliteWorldStore(connection, fence)
    bibles = SqliteBibleStore(connection, fence)
    casts = SqliteCastStore(connection, fence)
    narrative = SqliteNarrativeStore(connection, fence)
    created = gold.seed_gold_world(
        connection,
        world_store=worlds,
        bible_store=bibles,
        cast_store=casts,
        now=_NOW,
    )
    assert created.__class__.__name__ == "Ok"
    pipeline = gold.build_gold_pipeline(
        connection,
        world_store=worlds,
        cast_store=casts,
        bible_store=bibles,
        narrative_store=narrative,
        completion=gold.gold_completion(),
    )
    assert pipeline.plan_chapter(gold.WORLD_ID, _NOW).__class__.__name__ == (
        "Ok"
    )
    # the crash window: the gate is driven, the continuation is not.
    script = gold.gold_beats_by_scene()[gold.S1]
    driven = pipeline.run_scene(gold.S1, script[:3], _NOW)
    assert driven.__class__.__name__ == "Ok"
    gate_row = get_gate(connection, gold.GATE)
    assert gate_row is not None and gate_row.status is GateStatus.COMMITTED
    assert _read(
        app_db,
        "SELECT COUNT(*) FROM narrative_passage WHERE scene_id = ?",
        (gold.S1,),
    ) == (2,)
    connection.close()

    with v3_stack(app_db) as stack:
        state = stack.state()
        assert state["next"]["kind"] == "gate"
        assert state["controls"]["can_submit"] is True
        assert "续跑" in state["next"]["detail"]
        # continue will not re-drive a stored submission — it says so.
        refused = stack.advance()[1]
        assert refused["ok"] is False
        assert "durable 面优先" in refused["error"]
        # the empty-body re-drive finishes the ruling from canon.
        status, finished = stack.submit({})
        assert status == 200
        assert finished["ok"] is True, finished["error"]
        assert finished["did"]["closed_gates"] == [gold.GATE]
        assert finished["did"]["passage_ids"] == [f"{gold.S1}-p0003"]
        # no second ruling and no re-generated prose: the resolver was
        # asked once (the fixture's own drive), the writer once (the
        # continuation).
        assert stack.post.prompts("resolver") == []
        assert len(stack.post.prompts("writer")) == 1
        assert _count(app_db, "narrative_passage") == 3
        assert _read(
            app_db,
            "SELECT COUNT(*) FROM user_action WHERE gate_id = ?",
            (gold.GATE,),
        ) == (1,)


def test_the_provider_failure_is_a_payload_sentence(tmp_path: Path) -> None:
    """A dead transport is a 200 payload sentence (the runtime-fact
    posture), never a 500 and never a fabricated passage; the retry is
    available because the position is the rows."""

    class _Dead:
        def __call__(
            self,
            url: str,
            headers: Mapping[str, str],
            body: bytes,
            timeout: float,
        ) -> tuple[int, bytes]:
            raise OSError("the endpoint is gone")

    transport = _Dead()
    provider = OpenAICompatibleProvider(
        OpenAICompatibleConfig(
            base_url="https://egress.invalid/v1",
            model="scripted-model",
            secret_ref=SecretRef("test-key-ref"),
        ),
        FixedSecret(value="sk-offline-sentinel-NEVER-LEAK"),
        transport=transport,
    )
    app_db = tmp_path / "app.db"
    with v3_stack(app_db, provider=provider) as stack:
        started = stack.start()
        assert started["ok"] is False
        assert "设置" in started["error"]
        # the world's seed landed anyway (the two halves are separate
        # durable facts; the replay of start converges).
        assert stack.state()["world"]["exists"] is True
        assert stack.state()["chapter"] is None
        assert _count(app_db, "narrative_passage") == 0
        # an unconfigured endpoint (an OpenAI-shaped provider with no
        # coordinates) names the settings face, not a trace.
        blank = OpenAICompatibleProvider(
            OpenAICompatibleConfig(
                base_url="", model="", secret_ref=SecretRef("test-key-ref")
            ),
            FixedSecret(value="sk-offline-sentinel-NEVER-LEAK"),
        )
        with v3_stack(app_db, provider=blank) as second:
            refused = second.start()
            assert refused["ok"] is False
            assert "模型端点还没配置" in refused["error"]
        # a provider that is not an OpenAI-shaped one at all says so.
        with v3_stack(
            app_db,
            provider=ScriptedPersonaProvider(
                script=(ProviderOutput(text="x"),)
            ),
        ) as third:
            refused = third.start()
            assert refused["ok"] is False
            assert "没有接 OpenAI 兼容的模型端点" in refused["error"]


# ---------------------------------------------------------------------------
# 4. the poll posture (the /api/teaching/current exception)
# ---------------------------------------------------------------------------


def test_the_state_poll_is_served_off_the_work_queue(
    tmp_path: Path,
) -> None:
    """While a drive holds the work queue (a writer call blocked inside
    the transport), ``/api/v3/state`` still answers — it runs on its own
    short read-only connection, exactly like the teaching poll. A queued
    read would sit behind the drive for its whole round trip."""

    release = threading.Event()
    post = _GoldPost(release=release)
    app_db = tmp_path / "app.db"
    with v3_stack(app_db, post=post) as stack:
        assert stack.start()["ok"] is True
        answers: list[dict[str, Any]] = []

        def drive() -> None:
            answers.append(stack.advance()[1])

        driver = threading.Thread(target=drive, daemon=True)
        driver.start()
        try:
            assert post.blocked.wait(timeout=30.0), "the drive never started"
            # the worker is blocked mid-writing; the poll answers anyway.
            state = stack.state()
            assert state["ok"] is True
            assert state["world"]["exists"] is True
        finally:
            release.set()
            driver.join(timeout=60.0)
        assert not driver.is_alive()
        assert answers[0]["ok"] is True
        assert len(answers[0]["passages"]) == 1


# ---------------------------------------------------------------------------
# 5. the honest faces and the grammars
# ---------------------------------------------------------------------------


def test_a_host_without_the_v3_legs_answers_one_sentence() -> None:
    """The face built over a stub (no connection, no stores) answers the
    honest sentence for every route — never a traceback, never a
    fabricated payload. The off-queue poll does the same for an
    unreadable app.db."""

    face = NarrativeWebFace(object(), clock=lambda: _NOW)
    for payload in (
        face.state(),
        face.start(),
        face.advance(False),
        face.submit({}),
        face.settle(),
        face.next_chapter(),
        face.ack(["x"]),
    ):
        assert payload["ok"] is False
        assert "没有 V3 世界腿" in payload["error"]

    unreadable = narrative_state_ro(str(REPO / "no-such-app.db"))
    assert unreadable["ok"] is False
    assert "没有成功" in unreadable["error"]


def test_the_route_grammars_are_fail_closed(tmp_path: Path) -> None:
    """Bad bodies are 400s with one human sentence; the empty-body forms
    are the routes' own (their durable state is the request)."""

    app_db = tmp_path / "app.db"
    with v3_stack(app_db) as stack:
        stack.start()
        stack.advance()
        status, payload = _post_json(
            stack.port, "/api/v3/continue", {"end_scene": 1}
        )
        assert status == 400
        assert "end_scene" in payload["error"]
        status, payload = _post_json(
            stack.port, "/api/v3/submit", {"submission_id": "x"}
        )
        assert status == 400
        assert "intent_text" in payload["error"]
        status, payload = _post_json(
            stack.port, "/api/v3/ack", {"passage_ids": "one"}
        )
        assert status == 400
        assert "passage_ids" in payload["error"]
        # the anchored scene refuses the open-scene close flag.
        refused = stack.advance(end_scene=True)[1]
        assert refused["ok"] is False
        assert "作者脚本定席" in refused["error"]
        # an unknown api path stays the house 404.
        request = urllib.request.Request(
            f"http://127.0.0.1:{stack.port}/api/v3/nope"
        )
        status, payload = _open_request(request)
        assert status == 404
        assert payload["error"] == "not found"


# ---------------------------------------------------------------------------
# 6. the page half
# ---------------------------------------------------------------------------


def test_the_reading_page_is_served_and_the_main_ui_is_untouched(
    tmp_path: Path,
) -> None:
    """``/v3`` serves the reader page over the static allowlist, its two
    assets are byte-equal to the repo's own, and the main shell carries
    neither an entry nor a reference to the reading face (the main UI is
    untouched; the URL is the only door)."""

    app_db = tmp_path / "app.db"
    with v3_stack(app_db) as stack:
        status, _ctype, body = _raw(stack.port, "/v3")
        assert status == 200
        page = body.decode("utf-8")
        assert "试读" in page
        assert '<script type="module" src="/static/reader.js"></script>' in page
        assert '<link rel="stylesheet" href="/static/reader.css">' in page
        assert "<style" not in page and "<script>" not in page
        assert "http://" not in page and "https://" not in page
        for name, kind in (
            ("reader.css", "text/css"),
            ("reader.js", "text/javascript"),
        ):
            status, ctype, asset = _raw(stack.port, f"/static/{name}")
            assert status == 200
            assert ctype.startswith(kind)
            assert asset == (WEBUI / name).read_bytes()
            text = asset.decode("utf-8")
            assert "http://" not in text and "https://" not in text
        # the main shell: no entry, no reference.
        index = (WEBUI / "index.html").read_text(encoding="utf-8")
        app_js = (WEBUI / "app.js").read_text(encoding="utf-8")
        assert "/v3" not in index
        assert "reader" not in index
        assert "/v3" not in app_js
        assert "reader" not in app_js
        # and the shell is still served byte-equal (nothing was rewritten
        # at serve time).
        status, _ctype, served_root = _raw(stack.port, "/")
        assert status == 200
        assert served_root == (WEBUI / "index.html").read_bytes()


def _raw(port: int, path: str) -> tuple[int, str, bytes]:
    with _OPENER.open(
        f"http://127.0.0.1:{port}{path}", timeout=30
    ) as response:
        return (
            response.status,
            response.headers.get("Content-Type") or "",
            response.read(),
        )


# ---------------------------------------------------------------------------
# 7. the ledger and the cold-start discipline
# ---------------------------------------------------------------------------


def test_the_reading_face_starts_cold() -> None:
    """The P4-3 cold-start discipline (a new cross-package import face —
    persona + world on one assembly module): ``elc.narrative_web``
    imports in a fresh interpreter, and the package root does not
    re-export it."""

    env = dict(
        os.environ,
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=str(REPO / "src"),
    )
    proc = subprocess.run(
        [sys.executable, "-c", "import elc.narrative_web"],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    root = (REPO / "src" / "elc" / "__init__.py").read_text(encoding="utf-8")
    for keyword in ("narrative_web", "NarrativeWebFace"):
        assert keyword not in root


def test_the_ledger_carries_the_v3_8e_entries() -> None:
    """AOCI maintenance, pinned: the new module rides its own ledger
    entry with the faces this cut owns, and the web entry carries the new
    route family."""

    lines = (REPO / "aoci.code.txt").read_text(encoding="utf-8").split("\n")
    hits = [line for line in lines if line.startswith("narrative_web.py[")]
    assert len(hits) == 1, len(hits)
    entry = hits[0]
    for keyword in (
        "PersonaEgressCompletion",
        "NarrativeWebFace",
        "DurableReplayWriter",
        "DurableReplayResolver",
        "record_exposure",
        "durable",
        "V3-8e",
    ):
        assert keyword in entry, keyword
    web_hits = [line for line in lines if line.startswith("web.py[EC8L]")]
    assert len(web_hits) == 1
    for keyword in (
        "/api/v3/state",
        "reader.html",
        "NarrativeWebFace",
        "narrative_state_ro",
    ):
        assert keyword in web_hits[0], keyword
