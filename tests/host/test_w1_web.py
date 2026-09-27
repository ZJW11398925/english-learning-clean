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
   body outside the V1 grammar is a 400.
"""

from __future__ import annotations

import contextlib
import io
import json
import socket
import sqlite3
import threading
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
from elc.persona.types import ProviderOutput
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
from elc.teaching.rollout import RolloutStage
from elc.teaching.types import MomentState
from elc.user_config.types import (
    LearningGoal,
    LearningGoalPortfolio,
    TeachingFrequency,
    TeachingPolicyProfile,
)
from elc.web import _build_server, _commit, _WebFace, run_web
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
            # close() already ran on the worker thread (its finally); this is
            # the no-op repeat that proves the stack ended whole.
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
        assert '<input id="text"' in page
        assert "/api/turn" in page
        assert "/api/observations" in page
        assert "/api/history" in page
        # the W-2 reply face on the page: the skip button and its call
        assert "/api/teaching_reply" in page
        assert "跳过教学" in page


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

    assert _WebFace(_UnitHost(), "web-test")._moment_title(EV_TARGET) == EV_TARGET

    class _StorelessHost:
        content_store: Any = None

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
    §5.2 hard-opening cooldown (BF-03 §17, a declared 1800 s window from
    the first moment's opening), **not** the lock. Act two contracts that
    declared constant (``elc.teaching.budget.COOLDOWN_WINDOW_SECONDS = 0``
    — an implementation-declared default whose own docstring awaits a
    calibration; no gate or budget face is touched) and re-sends the
    second error text: the second moment opens on the other target —
    proof the lock, once skipped, never blocks teaching again.
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
        }


class _ReplyStubHost:
    """A host whose lock read answers one canned row (or None), and whose
    coordinator records whether a reply was submitted — the unit seam the
    reply face's pre-submit check is pinned against."""

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
    assert answer == {"accepted": True, "moment_state": "CLOSED", "error": None}

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
    """Bodies outside the V1 grammar are bad requests: no JSON, no
    ``control`` key, and any control word other than ``skip`` (V1 carries
    the skip control only) — and none of them commits anything."""

    with web_stack(tmp_path / "app.db") as stack:
        status, data = stack.post_raw("/api/teaching_reply", b"not json")
        assert status == 400
        assert "error" in data
        status, data = stack.post("/api/teaching_reply", {"nope": 1})
        assert status == 400
        status, data = stack.post("/api/teaching_reply", {"control": "attempt"})
        assert status == 400
        assert "skip" in data["error"]
        status, payload = stack.get_json("/api/history")
        assert status == 200
        assert payload["turns"] == []


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
