"""W-1 — the minimal local web face, over the production assembly.

The server is the real ``elc.web.run_web`` (``ThreadingHTTPServer`` bound to
127.0.0.1, work shipped to the host's thread), reached with ``urllib`` over
the loopback; the host is the real ``open_host`` — for the online legs the
full chain over the pilot ``content.db`` with ``Study-first`` declared and
the §5.1 policy + goal portfolio + §5.2 ``NOT_SCHEDULED`` row written through
the host's own controllers (the D-6-a online setup, unchanged). The one
environmental guard: the loopback opener is built with an empty proxy map, so
a developer's ``http_proxy`` can never stand between the test and the page.

Pinned here (the six VAL groups):

1. the page — GET ``/`` answers 200 text/html with the title, an input, and
   the three API calls the page makes;
2. the turn contract — POST ``/api/turn`` answers the four fields, and a
   clean turn on the online chain opens no moment;
3. the online chain end to end — the error text opens exactly one moment,
   focused on ``res-discourse-anyway``, read through the durable lineage;
4. the observations face answers the CLI readings core's numbers over the
   same app.db (one core, two faces — and the value pins);
5. the history face serves the turns the page sent, in order;
6. the structural pins — loopback-only bind, the CLI envelope shape kept,
   the human exit 2 for a missing ``--base-url`` (via both command entries),
   and a malformed body being a 400 that commits no turn;
7. the W-1R human face — the card title read out of content.db (the target's
   own words; the raw id on any read failure), the Chinese status/kind
   words, and the page's rendering of the human card line;
8. the W-2 teaching reply face — the skip control releases the
   ``AWAITING_USER`` moment's lock through the coordinator's own
   ``respond_to_teaching`` entry (the day-one deadlock closed end to end:
   skip, lock 0, the next error text opens a second moment), a skip with
   no open moment is refused as a runtime fact (never an HTTP error), a
   reply is submitted only against a moment at ``AWAITING_USER``, and a
   body outside the reply grammar is a 400;
9. the W-2 disposition — a web restart runs the startup recovery sweep
   (the dead epoch's orphan moment closes ``SYSTEM_RECOVERY_ABORT``, the
   lock is gone, before the bind), and the calibrated sixty-second
   cooldown still answers ``HARD_COOLDOWN_ACTIVE`` on the first post-skip
   retry (the calibration is a real window, not a silent open);
10. the W-3 attempt face — the user's own sentence goes through the same
    reply protocol as the skip (``CONTINUE`` carrying the attempt
    payload): a miss is judged FAILURE and re-prompts (the moment
    returns to ``AWAITING_USER`` with the lock held), the canonical
    answer completes the moment and releases the lock end to end (the
    durable lock row gone, the durable moment agreeing, teaching opening
    again once the calibrated cooldown is contracted), the verdict is
    the reply result's own evaluation word passed through readable
    (``feedback``; ``None`` when the reply carried no evaluation — never
    a fabricated one), and the attempt grammar (a non-empty ``text``)
    and the skip/attempt routing are pinned at both the HTTP and the
    envelope seam;
11. the W-4 immediacy face — ``/api/teaching/current`` runs off the work
    queue (a read-only poll on the handler thread over its own
    connection), so a poll during a turn's model generation answers in
    under a second and sees the ``OPENING`` card ("教学开启中…") before the
    reply lands; the replaced reload contract keeps its shape over the ro
    path (seven fields, ``{"moment": None}`` when nothing is open or the
    database is unreadable — never a 500), the title being the ro face's
    declared narrowing (the target's spoken name out of its id), and the
    page sends its placeholder line ("生成中…") plus the poll the instant a
    turn goes out.
"""

from __future__ import annotations

import contextlib
import io
import json
import socket
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

import elc.cli
import elc.teaching.budget
from elc.cli import main as cli_main
from elc.cli import observation_drift_count, observation_sections
from elc.content.build import build_content_db
from elc.detection import DetectorRegistry
from elc.detection.pilot import PILOT_VERSION, register_pilot
from elc.host import open_host
from elc.persona.provider import ScriptedPersonaProvider
from elc.persona.types import CompiledPrompt, ProviderOutput
from elc.platform.types import (
    ConversationId,
    EvidenceModality,
    GoalId,
    GoalModality,
    GoalVersion,
    Ok,
    PolicyVersion,
    TargetId,
)
from elc.teaching.envelope import TeachingControlIntent
from elc.teaching.rollout import RolloutStage
from elc.teaching.types import MomentState
from elc.user_config.types import (
    LearningGoal,
    LearningGoalPortfolio,
    TeachingFrequency,
    TeachingPolicyProfile,
)
from elc.web import _build_server, _commit, _current_teaching_ro, _WebFace, run_web
from elc.web import main as web_main

REPLY = "w1 web reply"
CONV = ConversationId("web-test")
CLEAN_TEXT = "The meeting starts at nine."
SECOND_TEXT = "I will call you tomorrow."
ERROR_TEXT = "Any way, let's continue with the plan."
EV_TARGET = "res-discourse-anyway"
#: The second day-one-deadlock arm: after the first moment is skipped the
#: lock is gone, so a *different* target's error text must open a fresh
#: moment ("get it," fronted with a pause → res-pragmatic-got-it).
SECOND_ERROR_TEXT = "Get it, I will send the file tonight."
EV_SECOND_TARGET = "res-pragmatic-got-it"

#: The W-3 attempt pair, against ``EV_TARGET``'s authored answer key
#: (content.db's ``teaching_content``: the canonical form is "Anyway,
#: let's get back to the topic."): a sentence that misses the key (the
#: evaluator answers FAILURE and the moment re-prompts) and the canonical
#: form itself (the evaluator answers SUCCESS and the moment completes).
ATTEMPT_MISS = "I got it, thanks."
ATTEMPT_HIT = "Anyway, let's get back to the topic."

#: The loopback opener: an empty proxy map, so a developer's ``http_proxy``
#: (this machine runs one) can never stand between the test and the page.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _get_json(port: int, path: str) -> tuple[int, Any]:
    with _OPENER.open(
        f"http://127.0.0.1:{port}{path}", timeout=30
    ) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def _get_raw(port: int, path: str) -> tuple[int, str, bytes]:
    with _OPENER.open(
        f"http://127.0.0.1:{port}{path}", timeout=30
    ) as response:
        return (
            response.status,
            response.headers.get("Content-Type") or "",
            response.read(),
        )


def _post_json(port: int, path: str, payload: Any) -> tuple[int, Any]:
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return _open_request(request)


def _post_raw(port: int, path: str, body: bytes) -> tuple[int, Any]:
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return _open_request(request)


def _open_request(request: urllib.request.Request) -> tuple[int, Any]:
    try:
        with _OPENER.open(request, timeout=30) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


@dataclass
class _Stack:
    """One serving stack: the port to hit, and the thread to stop."""

    port: int
    stop: threading.Event
    thread: threading.Thread
    box: dict[str, Any]

    def get_json(self, path: str) -> tuple[int, Any]:
        return _get_json(self.port, path)

    def get_raw(self, path: str) -> tuple[int, str, bytes]:
        return _get_raw(self.port, path)

    def post(self, path: str, payload: Any) -> tuple[int, Any]:
        return _post_json(self.port, path, payload)

    def post_raw(self, path: str, body: bytes) -> tuple[int, Any]:
        return _post_raw(self.port, path, body)


@contextlib.contextmanager
def web_stack(
    app_db: Path,
    *,
    content_db: Path | None = None,
    stage: RolloutStage | None = None,
    seed: Any = None,
) -> Iterator[_Stack]:
    """Serve one host until the with-block ends.

    The host's whole lifecycle — open, seed, serve, close — lives on the
    worker thread, because that is the one thread the work loop runs host
    touches on (``elc.web``'s one-thread rule; sqlite3 answers only the
    thread that opened the connection). A worker failure before the bind is
    re-raised on the test thread instead of timing out.
    """

    port = _free_port()
    ready = threading.Event()
    stop = threading.Event()
    box: dict[str, Any] = {}

    def worker() -> None:
        try:
            host = open_host(
                app_db,
                provider=ScriptedPersonaProvider(
                    script=(ProviderOutput(text=REPLY),)
                ),
                content_db_path=content_db,
                rollout_stage=stage,
            )
            box["host"] = host
            opened = host.open_conversation(CONV)
            assert isinstance(opened, Ok), opened
            if seed is not None:
                seed(host)
            run_web(
                host, port, conversation=str(CONV), ready=ready, stop=stop
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
        yield _Stack(port=port, stop=stop, thread=thread, box=box)
    finally:
        stop.set()
        thread.join(timeout=60.0)
        assert not thread.is_alive(), "the web worker did not stop"
        host = box.get("host")
        if host is not None and "error" not in box:
            # The worker thread has exited without closing its host (no
            # close() runs on this path — the connections die with the
            # daemon thread); this block stays the no-op it always was.
            pass


@pytest.fixture(scope="module")
def pilot_content_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("w1-pilot") / "content.db"
    registry = DetectorRegistry()
    register_pilot(registry)
    build_content_db(
        path,
        detector_registry=registry,
        verification_pilot_version=PILOT_VERSION,
    )
    return path


def seed_online(host: Any) -> None:
    """The D-6-a online setup, unchanged: §5.1 policy + goal portfolio, then
    the §5.2 NOT_SCHEDULED row — all through the host's own controllers."""

    written = host.user_config.upsert_teaching_policy(
        TeachingPolicyProfile(
            teaching_policy_profile_id=host.user_id,
            policy_version=PolicyVersion("pv-w1"),
            teaching_frequency=TeachingFrequency.BALANCED,
        )
    )
    assert isinstance(written, Ok), written
    portfolio = host.user_config.upsert_goal_portfolio(
        LearningGoalPortfolio(
            goal_portfolio_id=host.user_id,
            goal_version=GoalVersion("gv-w1"),
            goals=(
                LearningGoal(
                    goal_id=GoalId("goal-w1"),
                    goal_modality=GoalModality.SPEAKING,
                    description="a long-term goal",
                ),
            ),
            modality_weights={GoalModality.SPEAKING: 1.0},
            assessment_targets=(),
            effective_from=datetime.now(tz=UTC).isoformat(),
        )
    )
    assert isinstance(portfolio, Ok), portfolio
    row = host.curriculum.get_target(TargetId(EV_TARGET))
    assert isinstance(row, Ok), row
    scheduled = host.scheduler.recompute_schedule_item(
        row.value.target_type,
        TargetId(EV_TARGET),
        EvidenceModality(row.value.evidence_modality),
        datetime.now(tz=UTC).isoformat(),
    )
    assert isinstance(scheduled, Ok), scheduled


def seed_online_and_second_target(host: Any) -> None:
    """``seed_online`` plus the §5.2 row for the second deadlock arm's
    target: the real ``elc seed`` writes one row per EV target, and the
    deadlock closure needs a second target to be schedulable after the
    first moment is skipped (the W-1 scenarios never needed one)."""

    seed_online(host)
    row = host.curriculum.get_target(TargetId(EV_SECOND_TARGET))
    assert isinstance(row, Ok), row
    scheduled = host.scheduler.recompute_schedule_item(
        row.value.target_type,
        TargetId(EV_SECOND_TARGET),
        EvidenceModality(row.value.evidence_modality),
        datetime.now(tz=UTC).isoformat(),
    )
    assert isinstance(scheduled, Ok), scheduled


def run_cli(argv: list[str], **kwargs: Any) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = cli_main(argv, stdout=out, stderr=err, **kwargs)
    return code, out.getvalue(), err.getvalue()


# ---------------------------------------------------------------------------
# 1. the page


def test_the_page_serves_the_title_and_the_three_calls(
    tmp_path: Path,
) -> None:
    with web_stack(tmp_path / "app.db") as stack:
        status, content_type, body = stack.get_raw("/")
        assert status == 200
        assert content_type.startswith("text/html")
        page = body.decode("utf-8")
        assert "英语客厅 · Study-first dogfood" in page
        assert '<textarea id="text"' in page
        assert "/api/turn" in page
        assert "/api/observations" in page
        assert "/api/history" in page
        # the W-2 reply face on the page: the skip button and its call
        assert "/api/teaching_reply" in page
        assert "跳过这一题" in page


# ---------------------------------------------------------------------------
# 2. the turn contract (offline tier)


def test_a_turn_answers_the_full_json_contract(tmp_path: Path) -> None:
    with web_stack(tmp_path / "app.db") as stack:
        status, data = stack.post("/api/turn", {"text": CLEAN_TEXT})
        assert status == 200
        assert set(data) == {
            "reply",
            "turn_status",
            "failure_reason",
            "teaching_moments",
        }
        assert data["reply"] == REPLY
        assert data["turn_status"] == "COMPLETED"
        assert data["failure_reason"] is None
        assert data["teaching_moments"] == []


# ---------------------------------------------------------------------------
# 3. the online chain, end to end


def test_the_online_chain_opens_exactly_one_moment(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    with web_stack(
        tmp_path / "app.db",
        content_db=pilot_content_db,
        stage=RolloutStage.STUDY_FIRST,
        seed=seed_online,
    ) as stack:
        status, data = stack.post("/api/turn", {"text": ERROR_TEXT})
        assert status == 200
        assert data["reply"], data
        assert data["turn_status"] == "COMPLETED"
        assert data["teaching_moments"] == [
            {
                "focus_target_id": EV_TARGET,
                "lifecycle_state": "AWAITING_USER",
                "kind": "RESOURCE_PRACTICE",
                "title": (
                    "anyway — Signal that you are returning"
                    " to the main topic after a digression."
                ),
                "status_cn": "等待您回应",
                "kind_cn": "资源练习",
            }
        ]


def test_a_clean_text_opens_no_moment(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    with web_stack(
        tmp_path / "app.db",
        content_db=pilot_content_db,
        stage=RolloutStage.STUDY_FIRST,
        seed=seed_online,
    ) as stack:
        status, data = stack.post("/api/turn", {"text": CLEAN_TEXT})
        assert status == 200
        assert data["turn_status"] == "COMPLETED"
        assert data["teaching_moments"] == []


# ---------------------------------------------------------------------------
# 3b. the W-1R human face on the moment cards


def test_a_moment_card_carries_the_human_face(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """The card speaks: the title is the target's own words (the spoken
    name plus the authored function sentence, read out of content.db), the
    two vocabularies answer in Chinese, and the raw three fields survive
    untouched on top of the same moment."""

    with web_stack(
        tmp_path / "app.db",
        content_db=pilot_content_db,
        stage=RolloutStage.STUDY_FIRST,
        seed=seed_online,
    ) as stack:
        status, data = stack.post("/api/turn", {"text": ERROR_TEXT})
        assert status == 200
        (moment,) = data["teaching_moments"]
        assert moment["title"].startswith("anyway — ")
        assert "Signal that you are returning" in moment["title"]
        assert moment["status_cn"] == "等待您回应"
        assert moment["kind_cn"] == "资源练习"
        assert moment["focus_target_id"] == EV_TARGET
        assert moment["lifecycle_state"] == "AWAITING_USER"
        assert moment["kind"] == "RESOURCE_PRACTICE"


def test_an_unreadable_target_falls_back_to_the_raw_id(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """A failing content read is a plain card, never a broken turn.

    Three arms: a store whose read explodes answers the raw id; a host
    without a content store answers the raw id (the prep-1 tier); and over
    the real online chain a store swapped for an exploding delegate still
    answers 200 with the raw-id title (during a turn the web face is the
    only live reader of ``host.content_store`` — the teaching legs hold
    their own assembly-time references, so the swap reaches the card read
    and nothing else).
    """

    class _ExplodingStore:
        def get_teaching_content(self, entity_id: str) -> Any:
            raise RuntimeError(f"the content read exploded: {entity_id}")

    class _UnitHost:
        content_store: Any = _ExplodingStore()
        app_db_path = "stub-app.db"

    assert _WebFace(_UnitHost(), "web-test")._moment_title(EV_TARGET) == EV_TARGET

    class _StorelessHost:
        content_store: Any = None
        app_db_path = "stub-app.db"

    assert (
        _WebFace(_StorelessHost(), "web-test")._moment_title(EV_TARGET)
        == EV_TARGET
    )

    class _ExplodingDelegate:
        """Everything delegates to the real store; the card read explodes."""

        def __init__(self, real: Any) -> None:
            self._real = real

        def __getattr__(self, name: str) -> Any:
            if name == "get_teaching_content":
                raise RuntimeError("the content read exploded")
            return getattr(self._real, name)

    with web_stack(
        tmp_path / "app.db",
        content_db=pilot_content_db,
        stage=RolloutStage.STUDY_FIRST,
        seed=seed_online,
    ) as stack:
        host = stack.box["host"]
        real = host.content_store
        object.__setattr__(host, "content_store", _ExplodingDelegate(real))
        try:
            status, data = stack.post("/api/turn", {"text": ERROR_TEXT})
        finally:
            object.__setattr__(host, "content_store", real)
        assert status == 200
        (moment,) = data["teaching_moments"]
        assert moment["title"] == EV_TARGET
        assert moment["focus_target_id"] == EV_TARGET
        assert moment["status_cn"] == "等待您回应"


def test_the_page_renders_the_human_card_face(tmp_path: Path) -> None:
    """The embedded page renders the human card line — title first, Chinese
    state words — and keeps the raw-id row as the no-title fallback."""

    with web_stack(tmp_path / "app.db") as stack:
        status, content_type, body = stack.get_raw("/")
        assert status == 200
        page = body.decode("utf-8")
        assert "教学时刻：" in page
        assert "m.status_cn" in page
        assert "m.kind_cn" in page
        assert "if (m.title)" in page
        assert "m.focus_target_id" in page


# ---------------------------------------------------------------------------
# 3c. the W-2 teaching reply face — the skip control releases the lock


def _durable_teaching_face(
    app_db: Path,
) -> tuple[list[tuple], list[tuple]]:
    """The durable lock rows and moment states, read-only — what the
    reply face's answer must agree with."""

    ro = sqlite3.connect(f"file:{app_db}?mode=ro", uri=True)
    try:
        locks = ro.execute(
            "SELECT moment_id FROM active_teaching_lock"
            " WHERE conversation_id = ?",
            (str(CONV),),
        ).fetchall()
        moments = ro.execute(
            "SELECT moment_id, lifecycle_state FROM teaching_moment"
            " ORDER BY created_at, moment_id"
        ).fetchall()
    finally:
        ro.close()
    return locks, moments


def _gate_rows(app_db: Path) -> list[tuple]:
    """The durable gate decisions, read-only — what a DENY must name."""

    ro = sqlite3.connect(f"file:{app_db}?mode=ro", uri=True)
    try:
        return ro.execute(
            "SELECT decision, reason_codes FROM gate_decision"
            " ORDER BY created_at, gate_decision_id"
        ).fetchall()
    finally:
        ro.close()


def test_skipping_the_moment_releases_the_lock_and_teaching_resumes(
    tmp_path: Path, pilot_content_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The day-one deadlock, closed end to end — in two honest acts.

    Act one is the real configuration: the error text opens the moment and
    takes the lock (the deadlock's starting point — 36 teaching-less turns
    followed exactly this state); the skip control submits through the
    coordinator's own reply entry, the moment leaves ``AWAITING_USER``
    closed with ``USER_SKIP``, and the lock row is gone (the deadlock's
    blocker, released). The very next error text still opens no moment —
    and the durable gate row names the real reason: the canonical
    §5.2 hard-opening cooldown (BF-03 §17, a declared window from the
    first moment's opening — sixty seconds since the W-2 disposition's
    dogfood-era calibration), **not** the lock. Act two contracts that
    declared constant (``elc.teaching.budget.COOLDOWN_WINDOW_SECONDS = 0``
    — the implementation-declared window contracted for the moment, the
    same act the calibration performs at a finer grain; no gate or budget
    face is touched) and re-sends the second error text: the second moment
    opens on the other target — proof the lock, once skipped, never blocks
    teaching again.
    """

    app_db = tmp_path / "app.db"
    with web_stack(
        app_db,
        content_db=pilot_content_db,
        stage=RolloutStage.STUDY_FIRST,
        seed=seed_online_and_second_target,
    ) as stack:
        status, data = stack.post("/api/turn", {"text": ERROR_TEXT})
        assert status == 200
        (moment,) = data["teaching_moments"]
        assert moment["focus_target_id"] == EV_TARGET
        assert moment["lifecycle_state"] == "AWAITING_USER"
        locks, moments = _durable_teaching_face(app_db)
        assert len(locks) == 1
        assert [state for _, state in moments] == ["AWAITING_USER"]

        status, data = stack.post("/api/teaching_reply", {"control": "skip"})
        assert status == 200
        skip_answer = data
        assert skip_answer["accepted"] is True
        assert skip_answer["error"] is None
        assert skip_answer["moment_state"] != "AWAITING_USER"
        locks, moments = _durable_teaching_face(app_db)
        assert locks == []
        assert [state for _, state in moments] == [skip_answer["moment_state"]]

        # act one, closed: the lock is gone, and the next error text's
        # empty moment list is the cooldown's answer, named in the gate row
        status, data = stack.post("/api/turn", {"text": SECOND_ERROR_TEXT})
        assert status == 200
        assert data["turn_status"] == "COMPLETED"
        assert data["teaching_moments"] == []
        assert _gate_rows(app_db)[-1] == (
            "DENY",
            '["HARD_COOLDOWN_ACTIVE"]',
        )

        monkeypatch.setattr(
            elc.teaching.budget, "COOLDOWN_WINDOW_SECONDS", 0.0
        )
        status, data = stack.post("/api/turn", {"text": SECOND_ERROR_TEXT})
        assert status == 200
        (moment,) = data["teaching_moments"]
        assert moment["focus_target_id"] == EV_SECOND_TARGET
        assert moment["lifecycle_state"] == "AWAITING_USER"
        locks, moments = _durable_teaching_face(app_db)
        assert len(locks) == 1
        assert [state for _, state in moments] == [
            skip_answer["moment_state"],
            "AWAITING_USER",
        ]


def test_a_skip_with_no_open_moment_is_refused_not_an_error(
    tmp_path: Path,
) -> None:
    """No lock, no reply: the ordinary refusal (the button pressed twice,
    a stale page, a conversation with no teaching at all) answers
    ``accepted: false`` with the fixed sentence — a runtime fact, never
    an HTTP error."""

    with web_stack(tmp_path / "app.db") as stack:
        status, data = stack.post("/api/teaching_reply", {"control": "skip"})
        assert status == 200
        assert data == {
            "accepted": False,
            "moment_state": None,
            "error": "no open teaching moment",
            "feedback": None,
        }


class _ReplyStubHost:
    """A host whose lock read answers one canned row (or None), and whose
    coordinator records whether a reply was submitted — the unit seam the
    reply face's pre-submit check is pinned against."""

    #: the W-4 face copies this off any host it is handed (never read here)
    app_db_path = "stub-app.db"

    def __init__(self, row: tuple[str] | None) -> None:
        """``row`` mirrors the real read's shape: one column, the locked
        moment's lifecycle state (``None`` = no lock row)."""

        self._row = row
        self.submitted: list[Any] = []

    @property
    def db(self) -> "_ReplyStubHost":
        return self

    def execute(self, _sql: str, _params: Any) -> "_ReplyStubHost":
        return self

    def fetchone(self) -> tuple[str] | None:
        return self._row

    @property
    def coordinator(self) -> "_ReplyStubHost":
        return self

    def respond_to_teaching(self, request: Any) -> Any:
        self.submitted.append(request)
        return Ok(type("Completion", (), {"moment_state": MomentState.CLOSED})())


def test_a_reply_is_submitted_only_for_an_awaiting_moment() -> None:
    """The shape pin: the face checks the locked moment's state *before*
    it submits. An open ``AWAITING_USER`` moment submits (and passes the
    result's own state word through); a lock whose moment has already
    moved on is refused at the face with the fixed sentence and the
    coordinator is never called — a face that submits against any lock
    row goes red here."""

    awaiting = _ReplyStubHost(row=("AWAITING_USER",))
    answer = _WebFace(awaiting, str(CONV)).teaching_reply("skip")
    assert len(awaiting.submitted) == 1
    assert answer == {
        "accepted": True,
        "moment_state": "CLOSED",
        "error": None,
        "feedback": None,
    }

    moved_on = _ReplyStubHost(row=("EVALUATING",))
    answer = _WebFace(moved_on, str(CONV)).teaching_reply("skip")
    assert moved_on.submitted == []
    assert answer["accepted"] is False
    assert answer["error"] == "no open teaching moment"

    unlocked = _ReplyStubHost(row=None)
    answer = _WebFace(unlocked, str(CONV)).teaching_reply("skip")
    assert unlocked.submitted == []
    assert answer["accepted"] is False
    assert answer["error"] == "no open teaching moment"


def test_a_malformed_teaching_reply_body_is_a_400(tmp_path: Path) -> None:
    """Bodies outside the reply grammar are bad requests: no JSON, no
    ``control`` key, an unknown control word, and an attempt without a
    non-empty ``text`` (the W-3 grammar: an attempt carries the user's
    sentence) — and none of them commits anything."""

    with web_stack(tmp_path / "app.db") as stack:
        status, data = stack.post_raw("/api/teaching_reply", b"not json")
        assert status == 400
        assert "error" in data
        status, data = stack.post("/api/teaching_reply", {"nope": 1})
        assert status == 400
        status, data = stack.post("/api/teaching_reply", {"control": "attempt"})
        assert status == 400
        assert "text" in data["error"]
        status, data = stack.post(
            "/api/teaching_reply", {"control": "attempt", "text": "   "}
        )
        assert status == 400
        status, data = stack.post("/api/teaching_reply", {"control": "banana"})
        assert status == 400
        assert "skip" in data["error"]
        assert "attempt" in data["error"]
        status, payload = stack.get_json("/api/history")
        assert status == 200
        assert payload["turns"] == []


# ---------------------------------------------------------------------------
# 3d. the W-2 disposition — the restart sweep and the calibrated window


def _durable_moment_words(app_db: Path) -> list[tuple]:
    """The durable moment states with their abort words, read-only — the
    recovery sweep's exact answer."""

    ro = sqlite3.connect(f"file:{app_db}?mode=ro", uri=True)
    try:
        return ro.execute(
            "SELECT lifecycle_state, abort_reason FROM teaching_moment"
            " ORDER BY created_at, moment_id"
        ).fetchall()
    finally:
        ro.close()


def test_a_web_restart_sweeps_the_orphan_moment_of_the_dead_epoch(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """The second dogfood deadlock arm, closed in the real shape end to
    end. Act one: a host whose error-text turn opened the moment dies
    holding the lock — ``close()`` is the crash's honest stand-in, the
    durable rows outlive the process exactly as the dogfood run's did. Act
    two: the web comes back on a NEW host (a new epoch) and ``run_web``
    runs the startup recovery sweep after its open and before its bind —
    so by the time ``ready`` fires, the orphan moment has already left
    ``AWAITING_USER`` closed with ``SYSTEM_RECOVERY_ABORT`` and the lock
    row is gone. No request is served first: the sweep is the only actor
    between the death and the read."""

    app_db = tmp_path / "app.db"
    host_one = open_host(
        app_db,
        provider=ScriptedPersonaProvider(script=(ProviderOutput(text=REPLY),)),
        content_db_path=pilot_content_db,
        rollout_stage=RolloutStage.STUDY_FIRST,
    )
    try:
        opened = host_one.open_conversation(CONV)
        assert isinstance(opened, Ok), opened
        seed_online(host_one)
        completion = host_one.coordinator.begin_turn(
            _commit(CONV, ERROR_TEXT)
        )
        assert isinstance(completion, Ok), completion
        assert completion.value.turn_status.value == "COMPLETED"
        locks, moments = _durable_teaching_face(app_db)
        assert len(locks) == 1
        assert [state for _, state in moments] == ["AWAITING_USER"]
    finally:
        host_one.close()

    with web_stack(
        app_db,
        content_db=pilot_content_db,
        stage=RolloutStage.STUDY_FIRST,
    ):
        # nothing is posted: the sweep ran inside run_web before the bind,
        # so the durable face is already the recovery's answer
        locks, moments = _durable_teaching_face(app_db)
        assert locks == []
        assert _durable_moment_words(app_db) == [
            ("CLOSED", "SYSTEM_RECOVERY_ABORT")
        ]


def test_an_unavailable_sweep_is_said_out_loud_and_serving_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The chat startup's exact shape, kept: a recovery that refuses to
    scan at all is one line on stderr (``run_web`` has no stderr parameter
    of its own — the process's stderr is the honest place) and the page
    still serves — an unavailable sweep blocks the dogfood no more than it
    blocks chat. A run_web that deletes the line, or skips the call it
    reports, goes red here."""

    from elc.platform.types import DomainError, DomainErrorCode, Err
    from elc.web import run_web

    err = io.StringIO()
    port = _free_port()
    ready, stop = threading.Event(), threading.Event()
    box: dict[str, Any] = {}

    def refusing_sweep(_self: Any) -> Any:
        return Err(
            DomainError(
                code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                message="the sweep refused (injected)",
            )
        )

    def worker() -> None:
        host = open_host(
            tmp_path / "app.db",
            provider=ScriptedPersonaProvider(
                script=(ProviderOutput(text=REPLY),)
            ),
        )
        box["host"] = host
        try:
            with contextlib.redirect_stderr(err):
                run_web(
                    host, port, conversation=str(CONV), ready=ready, stop=stop
                )
        except BaseException as exc:
            box["error"] = exc
            ready.set()
        finally:
            host.close()

    # Host is a frozen dataclass: patch the class (monkeypatch restores
    # it), so run_web's own call answers the refusing stub.
    from elc.host import Host

    monkeypatch.setattr(Host, "startup_recovery", refusing_sweep)
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    try:
        assert ready.wait(timeout=60.0), "the web worker never became ready"
        assert "error" not in box, box.get("error")
        assert "elc web: startup recovery unavailable" in err.getvalue()
        assert "DEPENDENCY_UNAVAILABLE" in err.getvalue()
        assert "the sweep refused (injected)" in err.getvalue()
        status, data = _post_json(port, "/api/turn", {"text": CLEAN_TEXT})
        assert status == 200
        assert data["reply"] == REPLY
    finally:
        stop.set()
        thread.join(timeout=60.0)


def test_the_calibrated_cooldown_still_holds_right_after_the_skip(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """The W-2 disposition's calibration is a real window, not a silent
    open: within sixty seconds of the first moment's opening — the test's
    very next requests, no waiting — the second error text still opens no
    moment, and the durable gate row names the same canonical reason the
    thirty-minute default gave (``HARD_COOLDOWN_ACTIVE``). The calibrated
    value is pinned last, so the window cannot quietly revert: a revert to
    any other number would answer this test's next-turn question with a
    denial no dogfood sitting can wait out — or with no denial at all."""

    app_db = tmp_path / "app.db"
    with web_stack(
        app_db,
        content_db=pilot_content_db,
        stage=RolloutStage.STUDY_FIRST,
        seed=seed_online_and_second_target,
    ) as stack:
        status, data = stack.post("/api/turn", {"text": ERROR_TEXT})
        assert status == 200
        (moment,) = data["teaching_moments"]
        assert moment["lifecycle_state"] == "AWAITING_USER"

        status, data = stack.post("/api/teaching_reply", {"control": "skip"})
        assert status == 200
        assert data["accepted"] is True

        status, data = stack.post("/api/turn", {"text": SECOND_ERROR_TEXT})
        assert status == 200
        assert data["teaching_moments"] == []
        assert _gate_rows(app_db)[-1] == (
            "DENY",
            '["HARD_COOLDOWN_ACTIVE"]',
        )

    assert elc.teaching.budget.COOLDOWN_WINDOW_SECONDS == 60.0


# ---------------------------------------------------------------------------
# 3e. the W-3 attempt face — the user's sentence, judged


class _AttemptStubHost:
    """The attempt face's unit seam: a canned lock row (``None`` = no
    lock), a coordinator that records the submitted reply request, and a
    canned reply result whose evaluation verdict is configurable."""

    #: the W-4 face copies this off any host it is handed (never read here)
    app_db_path = "stub-app.db"

    def __init__(
        self, row: tuple[str] | None, evaluation_outcome: str | None = None
    ) -> None:
        self._row = row
        self._evaluation_outcome = evaluation_outcome
        self.submitted: list[Any] = []

    @property
    def db(self) -> "_AttemptStubHost":
        return self

    def execute(self, _sql: str, _params: Any) -> "_AttemptStubHost":
        return self

    def fetchone(self) -> tuple[str] | None:
        return self._row

    @property
    def coordinator(self) -> "_AttemptStubHost":
        return self

    def respond_to_teaching(self, request: Any) -> Any:
        self.submitted.append(request)
        fields: dict[str, Any] = {"moment_state": MomentState.CLOSED}
        if self._evaluation_outcome is not None:
            fields["evaluation_outcome"] = self._evaluation_outcome
        return Ok(type("Completion", (), fields)())


def test_an_attempt_submits_the_envelope_and_passes_the_verdict_through() -> None:
    """The attempt face's shape pins, at the unit seam.

    The user's sentence travels as the §4 envelope's attempt: CONTINUE
    (the control word a bare attempt carries — SM §4's attemptless
    controls are SKIP / REJECT_TARGET / CHANGE_TOPIC, and an envelope
    claiming one of those with an attempt attached is refused before any
    durable write), ``attempt_present=True``, and the payload's text is
    exactly the submitted string. The verdict is the runtime result's
    own word passed through readable — and a result with no evaluation
    answers ``feedback: None`` rather than a fabricated verdict. A skip
    still submits attemptless (the W-2 shape, unchanged)."""

    awaiting = _AttemptStubHost(
        row=("AWAITING_USER",), evaluation_outcome="SUCCESS"
    )
    answer = _WebFace(awaiting, str(CONV)).teaching_reply(
        "attempt", ATTEMPT_HIT
    )
    (request,) = awaiting.submitted
    assert request.envelope.control_intent is TeachingControlIntent.CONTINUE
    assert request.envelope.attempt_present is True
    assert request.envelope.attempt is not None
    assert request.envelope.attempt.text == ATTEMPT_HIT
    assert str(request.client_message_id).startswith("web-msg-")
    assert answer == {
        "accepted": True,
        "moment_state": "CLOSED",
        "error": None,
        "feedback": "SUCCESS（回答正确）",
    }

    silent = _AttemptStubHost(row=("AWAITING_USER",))
    answer = _WebFace(silent, str(CONV)).teaching_reply("attempt", "hello")
    assert len(silent.submitted) == 1
    assert answer["accepted"] is True
    assert answer["feedback"] is None

    skipping = _AttemptStubHost(row=("AWAITING_USER",))
    answer = _WebFace(skipping, str(CONV)).teaching_reply("skip")
    (request,) = skipping.submitted
    assert request.envelope.control_intent is TeachingControlIntent.SKIP
    assert request.envelope.attempt_present is False
    assert request.envelope.attempt is None
    assert answer["feedback"] is None


def test_an_attempt_is_judged_and_the_teaching_loop_stays_closed(
    tmp_path: Path, pilot_content_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The attempt loop, end to end over the real chain — the day-one
    dead end's last arm closed: the user answers, and the answer is
    judged.

    Act one: the miss is a runtime fact, not an error — accepted, judged
    (``feedback`` names the FAILURE verdict the evaluator produced
    against the target's own answer key), and the re-prompt returns the
    moment to ``AWAITING_USER`` with the lock still held (SM §1's
    "HINT / RETRY → AWAITING_USER": a miss asks again, it does not end
    the episode). Act two: the canonical sentence completes the moment —
    ``moment_state`` is the result's own word past ``AWAITING_USER``, the
    durable lock row is gone, the durable moment agrees, and the
    feedback carries the SUCCESS verdict. Act three: with the lock
    released, teaching can open again (the calibrated cooldown
    contracted exactly as the W-2 pin contracts it) — an answered moment
    never dead-ends the conversation's teaching."""

    app_db = tmp_path / "app.db"
    with web_stack(
        app_db,
        content_db=pilot_content_db,
        stage=RolloutStage.STUDY_FIRST,
        seed=seed_online_and_second_target,
    ) as stack:
        status, data = stack.post("/api/turn", {"text": ERROR_TEXT})
        assert status == 200
        (moment,) = data["teaching_moments"]
        assert moment["focus_target_id"] == EV_TARGET
        assert moment["lifecycle_state"] == "AWAITING_USER"

        status, data = stack.post(
            "/api/teaching_reply",
            {"control": "attempt", "text": ATTEMPT_MISS},
        )
        assert status == 200
        assert data["accepted"] is True
        assert data["error"] is None
        assert data["moment_state"] == "AWAITING_USER"
        assert data["feedback"] is not None
        assert "FAILURE" in data["feedback"]
        locks, moments = _durable_teaching_face(app_db)
        assert len(locks) == 1
        assert [state for _, state in moments] == ["AWAITING_USER"]

        status, data = stack.post(
            "/api/teaching_reply",
            {"control": "attempt", "text": ATTEMPT_HIT},
        )
        assert status == 200
        assert data["accepted"] is True
        assert data["error"] is None
        assert data["moment_state"] != "AWAITING_USER"
        assert data["feedback"] is not None
        assert "SUCCESS" in data["feedback"]
        locks, moments = _durable_teaching_face(app_db)
        assert locks == []
        assert [state for _, state in moments] == [data["moment_state"]]

        monkeypatch.setattr(
            elc.teaching.budget, "COOLDOWN_WINDOW_SECONDS", 0.0
        )
        status, data = stack.post("/api/turn", {"text": SECOND_ERROR_TEXT})
        assert status == 200
        (moment,) = data["teaching_moments"]
        assert moment["focus_target_id"] == EV_SECOND_TARGET
        assert moment["lifecycle_state"] == "AWAITING_USER"


def test_the_page_offers_the_attempt_box_and_the_skip_button(
    tmp_path: Path,
) -> None:
    """The AWAITING_USER card's W-3 face: the attempt box (the user's own
    English sentence) beside the skip button, and the page still keeps
    every word inert (textContent) — the attempt text travels as data,
    never as markup."""

    with web_stack(tmp_path / "app.db") as stack:
        status, content_type, body = stack.get_raw("/")
        assert status == 200
        page = body.decode("utf-8")
        assert "用英语试着造个句子…" in page
        assert "寄出作答" in page
        assert "跳过这一题" in page
        assert 'control: "attempt"' in page
        assert "已提交作答" in page
        # the card stays XSS-inert: textContent, never innerHTML
        assert "textContent" in page
        assert ".innerHTML" not in page


# ---------------------------------------------------------------------------
# 4. the observations face — the CLI readings core's numbers


def test_observations_answer_the_cli_core_over_the_same_db(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    app_db = tmp_path / "app.db"
    with web_stack(
        app_db,
        content_db=pilot_content_db,
        stage=RolloutStage.STUDY_FIRST,
        seed=seed_online,
    ) as stack:
        stack.post("/api/turn", {"text": ERROR_TEXT})
        status, payload = stack.get_json("/api/observations")
        assert status == 200
        assert payload["indicators"]
        ro = sqlite3.connect(f"file:{app_db}?mode=ro", uri=True)
        try:
            core = observation_sections(ro)
            drift = observation_drift_count(ro)
        finally:
            ro.close()
        assert payload["sections"] == [
            {
                "title": s.title,
                "rows": [list(row) for row in s.rows],
                "error": s.error,
            }
            for s in core
        ]
        assert payload["drift_count"] == drift == 0
        moment_rows = next(
            s
            for s in payload["sections"]
            if s["title"] == "teaching_moment by lifecycle_state"
        )
        assert moment_rows["rows"] == [["AWAITING_USER", "1"]]
        gate_rows = next(
            s
            for s in payload["sections"]
            if s["title"] == "gate_decision by decision × reason_codes"
        )
        assert gate_rows["rows"] == [["ALLOW", "[]", "1"]]


# ---------------------------------------------------------------------------
# 5. the history face


def test_history_serves_the_turns_the_page_sent(tmp_path: Path) -> None:
    with web_stack(tmp_path / "app.db") as stack:
        for text in (CLEAN_TEXT, SECOND_TEXT):
            status, _ = stack.post("/api/turn", {"text": text})
            assert status == 200
        status, payload = stack.get_json("/api/history")
        assert status == 200
        assert payload["turns"] == [
            {"user": CLEAN_TEXT, "assistant": REPLY},
            {"user": SECOND_TEXT, "assistant": REPLY},
        ]


# ---------------------------------------------------------------------------
# 6. the structural pins


def test_the_server_binds_loopback_only(tmp_path: Path) -> None:
    host = open_host(
        tmp_path / "app.db",
        provider=ScriptedPersonaProvider(script=(ProviderOutput(text=REPLY),)),
    )
    try:
        chosen = _free_port()
        server = _build_server(host, chosen, conversation=str(CONV))
        try:
            assert server.server_address == ("127.0.0.1", chosen)
        finally:
            server.server_close()
        ephemeral = _build_server(host, 0, conversation=str(CONV))
        try:
            address = ephemeral.server_address
            assert address[0] == "127.0.0.1"
            assert address[1] != 0
        finally:
            ephemeral.server_close()
    finally:
        host.close()


def test_the_web_envelope_is_shape_equal_to_the_cli_envelope() -> None:
    web_command = _commit(ConversationId("conv-x"), "hello there")
    cli_command = elc.cli._commit(ConversationId("conv-x"), "hello there")
    assert web_command.conversation_id == cli_command.conversation_id
    assert web_command.raw_content == cli_command.raw_content == "hello there"
    assert web_command.envelope.raw_payload == cli_command.envelope.raw_payload
    assert web_command.runtime_version == cli_command.runtime_version
    assert (
        web_command.envelope.interaction_channel
        == cli_command.envelope.interaction_channel
    )
    assert web_command.envelope.persona_id is None
    assert cli_command.envelope.persona_id is None
    assert web_command.envelope.scene_id is None
    assert cli_command.envelope.scene_id is None
    assert str(web_command.envelope.input_id).startswith("web-")
    assert str(cli_command.envelope.input_id).startswith("cli-")
    minted_again = _commit(ConversationId("conv-x"), "hello there")
    assert (
        minted_again.envelope.client_message_id
        != web_command.envelope.client_message_id
    )


def test_the_web_subcommand_refuses_a_missing_base_url(
    tmp_path: Path,
) -> None:
    app_db = tmp_path / "app.db"
    code, _, err = run_cli(["web", "--app-db", str(app_db)])
    assert code == 2
    assert "--app-db" in err and "required" in err
    assert not app_db.exists()


class _StubServeHost:
    """Just enough host for the web branch over a faked ``run_web``."""

    epoch = "epoch-stub"

    def close(self) -> None:
        return None


def test_the_web_command_passes_content_db_stage_and_port_through(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The web branch assembles exactly like chat: the operator's
    ``--content-db`` / ``--rollout-stage`` reach ``open_host`` verbatim (a
    stage forced to ``None`` here is the zero-open boundary broken) and the
    ``--port`` reaches ``run_web`` — one assembly path, pinned end to end."""

    received: dict[str, object] = {}
    captured: dict[str, object] = {}

    def recording_open_host(app_db_path: object, **kwargs: object) -> Any:
        received["app_db"] = app_db_path
        received.update(kwargs)
        return _StubServeHost()

    def fake_run_web(host: Any, port: int, **kwargs: object) -> None:
        captured["host"] = host
        captured["port"] = port
        captured.update(kwargs)

    monkeypatch.setattr(elc.cli, "open_host", recording_open_host)
    monkeypatch.setattr("elc.web.run_web", fake_run_web)
    content_db = tmp_path / "content.db"
    content_db.write_bytes(b"not a real artifact (open_host is stubbed)")
    code, _, err = run_cli(
        [
            "web",
            "--app-db",
            str(tmp_path / "app.db"),
            "--base-url",
            "https://offline.invalid/v1",
            "--model",
            "offline-model",
            "--api-key-env",
            "W1_UNSET_KEY_VAR",
            "--content-db",
            str(content_db),
            "--rollout-stage",
            "Study-first",
            "--port",
            "8977",
        ]
    )
    assert (code, err) == (0, "")
    assert received["content_db_path"] == str(content_db)
    assert received["rollout_stage"] is RolloutStage.STUDY_FIRST
    assert captured["port"] == 8977
    assert captured["host"] is not None


def test_the_two_faces_default_to_their_own_transcripts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MEDIUM-1 (review): the web face's documented isolation — its default
    conversation is ``web-default``, never the CLI's ``cli-default`` — must
    be behaviour, not prose. An explicit ``--conversation`` stays honoured
    on both faces."""

    web_conversation: dict[str, object] = {}
    monkeypatch.setattr(elc.cli, "open_host", lambda *a, **k: _StubServeHost())
    monkeypatch.setattr(
        "elc.web.run_web",
        lambda host, port, **kwargs: web_conversation.update(kwargs),
    )
    code, _, err = run_cli(
        [
            "web",
            "--app-db",
            str(tmp_path / "app.db"),
            "--base-url",
            "https://offline.invalid/v1",
            "--model",
            "offline-model",
            "--api-key-env",
            "W1_UNSET_KEY_VAR",
        ]
    )
    assert (code, err) == (0, "")
    assert web_conversation["conversation"] == "web-default"

    web_conversation.clear()
    code, _, err = run_cli(
        [
            "web",
            "--app-db",
            str(tmp_path / "app2.db"),
            "--base-url",
            "https://offline.invalid/v1",
            "--model",
            "offline-model",
            "--api-key-env",
            "W1_UNSET_KEY_VAR",
            "--conversation",
            "explicit-conv",
        ]
    )
    assert (code, err) == (0, "")
    assert web_conversation["conversation"] == "explicit-conv"


def test_the_cli_web_branch_answers_web_open_error_with_a_sentence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """LOW-1 (review): the human-sentence exit-1 branch for a refused
    conversation open is part of the fix — this pins it (its mutation,
    deleting the branch, left the whole suite green)."""

    from elc.web import WebOpenError

    monkeypatch.setattr(elc.cli, "open_host", lambda *a, **k: _StubServeHost())
    monkeypatch.setattr(
        "elc.web.run_web",
        lambda host, port, **kwargs: (_ for _ in ()).throw(
            WebOpenError("cannot open conversation x: NOT_FOUND: no")
        ),
    )
    err = io.StringIO()
    code = elc.cli.main(
        [
            "web",
            "--app-db",
            str(tmp_path / "app.db"),
            "--base-url",
            "https://offline.invalid/v1",
            "--model",
            "offline-model",
            "--api-key-env",
            "W1_UNSET_KEY_VAR",
        ],
        stderr=err,
    )
    assert code == 1
    assert "elc web: cannot open conversation" in err.getvalue()


def test_the_web_entry_delegates_to_the_same_command(tmp_path: Path) -> None:
    app_db = tmp_path / "app.db"
    err = io.StringIO()
    code = web_main(["--app-db", str(app_db)], stderr=err)
    assert code == 2
    assert "required" in err.getvalue()
    assert not app_db.exists()


def test_a_malformed_body_is_a_400_that_commits_no_turn(
    tmp_path: Path,
) -> None:
    with web_stack(tmp_path / "app.db") as stack:
        status, data = stack.post_raw("/api/turn", b"this is not json")
        assert status == 400
        assert "error" in data
        status, data = stack.post("/api/turn", {"no_text": ""})
        assert status == 400
        status, payload = stack.get_json("/api/history")
        assert status == 200
        assert payload["turns"] == []


# ---------------------------------------------------------------------------
# the live first-request form (controller-verified defect, fixed in-run):
# run_web opens the conversation itself
# ---------------------------------------------------------------------------


def test_run_web_opens_the_conversation_itself(tmp_path: Path) -> None:
    """The real CLI form — ``python -m elc web`` against a fresh app.db —
    has no other opener than run_web: the web_stack fixture pre-opens, so
    this test serves a host whose conversation was never opened and posts
    one turn. Before the fix every such turn answered
    ``NOT_FOUND: conversation not found``; now the reply is real."""

    from elc.web import run_web

    port = _free_port()
    ready, stop = threading.Event(), threading.Event()
    box: dict[str, Any] = {}

    def worker() -> None:
        try:
            host = open_host(
                tmp_path / "app.db",
                provider=ScriptedPersonaProvider(
                    script=(ProviderOutput(text=REPLY),)
                ),
            )
            box["host"] = host
            # NOTE: no open_conversation here — that is the point.
            run_web(host, port, conversation=str(CONV), ready=ready, stop=stop)
        except BaseException as exc:
            box["error"] = exc
            ready.set()
        finally:
            host = box.get("host")
            if host is not None and "error" not in box:
                host.close()

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    try:
        assert ready.wait(timeout=60.0), "the web worker never became ready"
        assert "error" not in box, box.get("error")
        body = json.dumps({"text": CLEAN_TEXT}).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/turn",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with _OPENER.open(req, timeout=30.0) as response:
            data = json.loads(response.read())
        assert data["reply"] == REPLY, data
        assert data["failure_reason"] is None, data
    finally:
        stop.set()
        thread.join(timeout=60.0)


def test_a_refused_conversation_open_raises_before_serving(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An open that refuses is chat's open-failure shape: run_web raises
    WebOpenError before binding, the CLI branch answers it with one human
    sentence and exit 1 — never a 500-per-request loop."""

    from elc.platform.types import DomainError, DomainErrorCode, Err
    from elc.web import WebOpenError, run_web

    host = open_host(
        tmp_path / "app.db",
        provider=ScriptedPersonaProvider(script=(ProviderOutput(text=REPLY),)),
    )
    try:
        # Host is a frozen dataclass: patch the class (monkeypatch restores
        # it), so the instance's call goes to the refusing stub.
        monkeypatch.setattr(
            type(host),
            "open_conversation",
            lambda _self, _cid: Err(
                DomainError(
                    code=DomainErrorCode.NOT_FOUND,
                    message="conversation refused (injected)",
                )
            ),
        )
        with pytest.raises(WebOpenError, match="conversation refused"):
            run_web(host, _free_port(), conversation=str(CONV))
    finally:
        host.close()


def test_the_web_command_prints_a_serving_banner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The controller fix for the silent-start defect: ``python -m elc web``
    prints where it is serving (and how to stop) before blocking — an
    operator must never face a silent prompt and guess the server is up.
    A busy port answers with the human sentence + exit 1, never a
    traceback."""

    monkeypatch.setattr(elc.cli, "open_host", lambda *a, **k: _StubServeHost())
    monkeypatch.setattr("elc.web.run_web", lambda host, port, **kw: None)
    out, err = io.StringIO(), io.StringIO()
    code = elc.cli.main(
        [
            "web",
            "--app-db",
            str(tmp_path / "app.db"),
            "--base-url",
            "https://offline.invalid/v1",
            "--model",
            "offline-model",
            "--api-key-env",
            "W1_UNSET_KEY_VAR",
            "--port",
            "8961",
        ],
        stdout=out,
        stderr=err,
    )
    assert code == 0
    assert "serving http://127.0.0.1:8961" in out.getvalue()
    assert "Ctrl+C" in out.getvalue()

    def busy(host: Any, port: int, **kwargs: Any) -> None:
        raise OSError(10048, "address already in use")

    monkeypatch.setattr("elc.web.run_web", busy)
    out2, err2 = io.StringIO(), io.StringIO()
    code2 = elc.cli.main(
        [
            "web",
            "--app-db",
            str(tmp_path / "app2.db"),
            "--base-url",
            "https://offline.invalid/v1",
            "--model",
            "offline-model",
            "--api-key-env",
            "W1_UNSET_KEY_VAR",
            "--port",
            "8962",
        ],
        stdout=out2,
        stderr=err2,
    )
    assert code2 == 1
    assert "cannot listen on 127.0.0.1:8962" in err2.getvalue()
    assert "--port" in err2.getvalue()

    def interrupted(host: Any, port: int, **kwargs: Any) -> None:
        raise KeyboardInterrupt()

    monkeypatch.setattr("elc.web.run_web", interrupted)
    out3, err3 = io.StringIO(), io.StringIO()
    code3 = elc.cli.main(
        [
            "web",
            "--app-db",
            str(tmp_path / "app3.db"),
            "--base-url",
            "https://offline.invalid/v1",
            "--model",
            "offline-model",
            "--api-key-env",
            "W1_UNSET_KEY_VAR",
        ],
        stdout=out3,
        stderr=err3,
    )
    # the banner promises "Ctrl+C to stop"; the stop answers with a clean
    # exit 0, never a traceback (review INFO-2, fixed with the banner)
    assert code3 == 0
    assert "Traceback" not in err3.getvalue()


def test_a_page_reload_recovers_the_open_teaching_card(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """The reload-recovery face (user's stranded-controls gap): the card a
    turn response rendered disappears on refresh, yet the moment is still
    open and still holds the lock — ``/api/teaching/current`` answers that
    same moment in the card's own shape (human fields included), and after
    a skip it answers ``{"moment": None}`` — a refresh can never strand an
    open teaching without its attempt box and skip button."""

    with web_stack(
        tmp_path / "app.db",
        content_db=pilot_content_db,
        stage=RolloutStage.STUDY_FIRST,
        seed=seed_online_and_second_target,
    ) as stack:
        status, data = stack.post("/api/turn", {"text": ERROR_TEXT})
        assert status == 200
        assert data["teaching_moments"], data

        status, payload = stack.get_json("/api/teaching/current")
        assert status == 200
        moment = payload["moment"]
        assert moment is not None
        assert moment["focus_target_id"] == EV_TARGET
        assert moment["lifecycle_state"] == "AWAITING_USER"
        # W-4: the current face is the read-only poll face now — its title
        # is the target's spoken name out of the id (the ro narrowing); the
        # hint-ladder sentence stays the turn card's own title.
        assert moment["title"] == "anyway"
        assert moment["status_cn"] == "等待您回应"
        assert moment["kind_cn"] == "资源练习"

        status, data = stack.post(
            "/api/teaching_reply", {"control": "skip"}
        )
        assert status == 200 and data["accepted"] is True

        status, payload = stack.get_json("/api/teaching/current")
        assert status == 200
        assert payload == {"moment": None}


# ---------------------------------------------------------------------------
# 11. the W-4 immediacy face — the read-only current poll off the work queue


@dataclass
class _SlowProvider:
    """A provider wrapper that stalls one wall-clock stretch per call.

    The stall stands in for the real model round trip (the 3–14 s the
    dogfood run measured); 1.5 s keeps both arms of the core pin far from
    the threshold — the queue arm cannot answer before the stall's
    remainder, the handler-thread arm answers in a request's time.
    """

    inner: ScriptedPersonaProvider
    seconds: float

    def call(self, prompt: CompiledPrompt) -> ProviderOutput:
        time.sleep(self.seconds)
        return self.inner.call(prompt)


@contextlib.contextmanager
def slow_stack(
    app_db: Path, content_db: Path, provider: Any
) -> Iterator[_Stack]:
    """``web_stack`` with a caller-chosen provider.

    The shared fixture pins the scripted provider (every other face runs
    deterministic); the W-4 core pin needs one that is slow on purpose, so
    it gets the same open → seed → serve → stop lifecycle with that one
    substitution — everything else (the real ``run_web``, the real
    ``open_host``, the worker-thread shape) is shared verbatim.
    """

    port = _free_port()
    ready = threading.Event()
    stop = threading.Event()
    box: dict[str, Any] = {}

    def worker() -> None:
        try:
            host = open_host(
                app_db,
                provider=provider,
                content_db_path=content_db,
                rollout_stage=RolloutStage.STUDY_FIRST,
            )
            box["host"] = host
            opened = host.open_conversation(CONV)
            assert isinstance(opened, Ok), opened
            seed_online(host)
            run_web(
                host, port, conversation=str(CONV), ready=ready, stop=stop
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
        yield _Stack(port=port, stop=stop, thread=thread, box=box)
    finally:
        stop.set()
        thread.join(timeout=60.0)
        assert not thread.is_alive(), "the web worker did not stop"


def test_during_a_slow_generation_the_current_face_stays_unblocked(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """The W-4 core pin: the read-only poll is answered **during** a turn's
    generation, off the work queue.

    Concurrency construction: a daemon thread POSTs the error text (the
    turn's closure occupies the host's thread for the whole 1.5 s provider
    stall); meanwhile the test thread polls ``/api/teaching/current`` in a
    0.05 s loop. The moment is durable at ``OPENING`` **before** the
    provider call, so every poll served on the handler thread must answer
    200 fast (well under 1 s — on the work queue the same poll would queue
    behind the turn and take at least the stall's remainder, ≈1.2 s past
    the first attempt) and must observe the ``OPENING`` card inside the
    window. After the turn lands, the same face answers the real
    ``AWAITING_USER`` card.
    """

    provider = _SlowProvider(
        ScriptedPersonaProvider(script=(ProviderOutput(text=REPLY),)), 1.5
    )
    with slow_stack(tmp_path / "app.db", pilot_content_db, provider) as stack:
        answer: dict[str, Any] = {}

        def post() -> None:
            answer["turn"] = stack.post("/api/turn", {"text": ERROR_TEXT})

        turner = threading.Thread(target=post, daemon=True)
        turner.start()
        deadline = time.monotonic() + 8.0
        opening: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            started = time.monotonic()
            status, payload = stack.get_json("/api/teaching/current")
            elapsed = time.monotonic() - started
            assert status == 200, payload
            assert elapsed < 1.0, (
                f"the poll queued behind the turn: {elapsed:.2f}s"
            )
            moment = payload["moment"]
            if moment is not None and moment["lifecycle_state"] == "OPENING":
                opening = moment
                break
            time.sleep(0.05)
        assert opening is not None, "the OPENING window was never observed"
        assert opening["focus_target_id"] == EV_TARGET
        assert opening["status_cn"] == "教学开启中…"

        turner.join(timeout=30.0)
        assert not turner.is_alive()
        status, data = answer["turn"]
        assert status == 200
        assert data["turn_status"] == "COMPLETED"
        assert data["teaching_moments"], data

        status, payload = stack.get_json("/api/teaching/current")
        assert status == 200
        assert payload["moment"] is not None
        assert payload["moment"]["lifecycle_state"] == "AWAITING_USER"
        assert payload["moment"]["status_cn"] == "等待您回应"


def test_the_current_face_answers_the_same_card_over_the_ro_path(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """The ro replacement keeps the reload contract: an open teaching
    answers 200 with the full card (all seven fields, the Chinese words), and
    an unreadable database answers ``{"moment": None}`` — a poll never
    raises, never 500s. The title is the ro face's declared narrowing: the
    target's spoken name out of its id (the hint-ladder sentence stays the
    turn card's, since content.db's path does not reach this face)."""

    with web_stack(
        tmp_path / "app.db",
        content_db=pilot_content_db,
        stage=RolloutStage.STUDY_FIRST,
        seed=seed_online,
    ) as stack:
        status, data = stack.post("/api/turn", {"text": ERROR_TEXT})
        assert status == 200
        assert data["teaching_moments"], data

        status, payload = stack.get_json("/api/teaching/current")
        assert status == 200
        moment = payload["moment"]
        assert moment is not None
        assert moment["focus_target_id"] == EV_TARGET
        assert moment["lifecycle_state"] == "AWAITING_USER"
        assert moment["kind"] == "RESOURCE_PRACTICE"
        assert moment["title"] == "anyway"
        assert moment["title"] != EV_TARGET
        assert moment["status_cn"] == "等待您回应"
        assert moment["kind_cn"] == "资源练习"

    # the ro face's own failure posture, unit-level: a database that does
    # not exist answers "nothing open" — no exception out, nothing to 500
    assert _current_teaching_ro(str(tmp_path / "absent.db"), "web-test") == {
        "moment": None
    }


def test_the_page_signals_generation_and_polls_the_current_face(
    tmp_path: Path,
) -> None:
    """The send-time UX pin, as strings the browser actually runs: a turn
    sent puts up the placeholder line and starts the moment poll, the poll
    hits the read-only current face every 400 ms with a 90 s cap, and the
    stop function ends it when the turn response lands."""

    with web_stack(tmp_path / "app.db") as stack:
        status, content_type, body = stack.get_raw("/")
        assert status == 200
        page = body.decode("utf-8")
    assert "（生成中…）" in page
    assert "startMomentPolling()" in page
    assert "stopMomentPolling()" in page
    assert "setInterval(" in page
    assert '"/api/teaching/current"' in page
    assert "MOMENT_POLL_MS = 400" in page
    assert "MOMENT_POLL_MAX_MS = 90000" in page
