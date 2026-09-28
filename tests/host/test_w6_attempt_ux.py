"""W-6 — the attempt loop, made legible (作答回路可感化).

The server, the host and the online seed are the W-1 suite's own fixtures
(one serving stack, one production assembly); this file pins only the W-6
face on top:

1. the three help arms over the real chain — ``{"control": "hint"}`` /
   ``{"control": "reveal"}`` / ``{"control": "explanation"}`` submit
   through the same reply entry, are accepted, and leave the moment
   ``AWAITING_USER`` with the lock held: a hint and an explanation are
   continuations by construction, and the reveal is pinned at its real
   runtime semantics — SM §3's ``POST_REVEAL_OPTIONAL_ATTEMPT`` phase
   (``FULL_REVEAL``) keeps the moment open after the answer shows; the
   durable rows name the delivery (``TEACHING_HINT`` /
   ``TEACHING_REVEAL`` / ``TEACHING_EXPLANATION``, the moment's
   ``presentation_phase``);
2. the reply grammar stays closed — an unknown control word is a 400
   whose sentence names all five words, and nothing durable happens;
3. the ro current card's ``last_attempt_feedback`` — ``None`` on a
   moment no attempt was judged against, the exact readable verdict
   (``FAILURE（未命中目标表达）``) after a judged miss, and still
   readable on the next GET (the refresh the field exists for);
4. the face-level mapping — each help word submits the runtime's own
   intent (``ASK_HINT`` / ``ASK_ANSWER`` / ``ASK_EXPLANATION``,
   ``attempt_present=False``, a fresh ``web-msg-`` id), and a word
   outside the grammar raises at the face instead of silently meaning
   SKIP (the HTTP layer 400s it first);
5. the page's own strings — the busy placeholder (``批改中…``), the
   three help buttons with the reveal confirm, the human fetch-failure
   line, the result-strip and busy machinery, and the ro field the
   refresh re-renders — with the card still XSS-inert (textContent,
   never innerHTML).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from elc.platform.types import Ok
from elc.teaching.envelope import TeachingControlIntent
from elc.teaching.rollout import RolloutStage
from elc.teaching.types import MomentState
from tests.host import test_w1_web
from tests.host.test_w1_web import (
    ATTEMPT_MISS,
    CONV,
    ERROR_TEXT,
    EV_TARGET,
    _WebFace,
    seed_online,
    web_stack,
)

#: The W-1 suite's module-scoped pilot ``content.db`` fixture, bound under
#: the same name so pytest resolves it for this module's tests too.
pilot_content_db = test_w1_web.pilot_content_db


def _durable_face(app_db: Path) -> tuple[list, list, list]:
    """The durable teaching facts a reply must agree with: the lock rows,
    the moments' presentation phases (oldest first) and the delivered
    teaching action types."""

    ro = sqlite3.connect(f"file:{app_db}?mode=ro", uri=True)
    try:
        locks = ro.execute(
            "SELECT moment_id FROM active_teaching_lock"
        ).fetchall()
        phases = [
            str(row[0])
            for row in ro.execute(
                "SELECT presentation_phase FROM teaching_moment"
                " ORDER BY created_at, moment_id"
            )
        ]
        actions = [
            str(row[0])
            for row in ro.execute(
                "SELECT action_type FROM generation_action_intent"
                " ORDER BY created_at"
            )
        ]
        return locks, phases, actions
    finally:
        ro.close()


def _open_moment(stack: Any) -> None:
    """One error-text turn over the online chain: the moment opens at
    ``AWAITING_USER`` holding the lock — the reply face's starting point."""

    status, data = stack.post("/api/turn", {"text": ERROR_TEXT})
    assert status == 200
    (moment,) = data["teaching_moments"]
    assert moment["focus_target_id"] == EV_TARGET
    assert moment["lifecycle_state"] == "AWAITING_USER"


# ---------------------------------------------------------------------------
# 1. the three help arms, end to end


def test_the_hint_arm_delivers_a_hint_and_keeps_the_moment_open(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    app_db = tmp_path / "app.db"
    with web_stack(
        app_db,
        content_db=pilot_content_db,
        stage=RolloutStage.STUDY_FIRST,
        seed=seed_online,
    ) as stack:
        _open_moment(stack)
        status, data = stack.post("/api/teaching_reply", {"control": "hint"})
        assert status == 200
        assert data["accepted"] is True
        assert data["error"] is None
        assert data["moment_state"] == "AWAITING_USER"
        assert data["feedback"] is None
        assert isinstance(data["delivery_text"], str) and data["delivery_text"]
        locks, phases, actions = _durable_face(app_db)
        assert len(locks) == 1
        assert phases == ["HINT_SEMANTIC"]
        assert actions[-1] == "TEACHING_HINT"


def test_the_reveal_arm_shows_the_answer_and_keeps_the_moment_open(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """The reveal arm at its real runtime semantics: an authorized
    user-requested reveal does **not** close the moment — SM §3's
    ``POST_REVEAL_OPTIONAL_ATTEMPT`` phase keeps it open at
    ``FULL_REVEAL`` with the lock held, so the card can offer the
    post-reveal optional attempt. (The task book expected
    ``CLOSED``/lock released; the runtime's own pipeline decides, and the
    probe run behind this pin is the receipt's objection evidence.)"""

    app_db = tmp_path / "app.db"
    with web_stack(
        app_db,
        content_db=pilot_content_db,
        stage=RolloutStage.STUDY_FIRST,
        seed=seed_online,
    ) as stack:
        _open_moment(stack)
        status, data = stack.post("/api/teaching_reply", {"control": "reveal"})
        assert status == 200
        assert data["accepted"] is True
        assert data["error"] is None
        assert data["moment_state"] == "AWAITING_USER"
        assert isinstance(data["delivery_text"], str) and data["delivery_text"]
        locks, phases, actions = _durable_face(app_db)
        assert len(locks) == 1
        assert phases == ["FULL_REVEAL"]
        assert actions[-1] == "TEACHING_REVEAL"
        # the ro card still serves the open moment — and no verdict exists
        status, payload = stack.get_json("/api/teaching/current")
        assert status == 200
        assert payload["moment"]["lifecycle_state"] == "AWAITING_USER"
        assert payload["moment"]["last_attempt_feedback"] is None


def test_the_explanation_arm_delivers_an_explanation(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    app_db = tmp_path / "app.db"
    with web_stack(
        app_db,
        content_db=pilot_content_db,
        stage=RolloutStage.STUDY_FIRST,
        seed=seed_online,
    ) as stack:
        _open_moment(stack)
        status, data = stack.post(
            "/api/teaching_reply", {"control": "explanation"}
        )
        assert status == 200
        assert data["accepted"] is True
        assert data["moment_state"] == "AWAITING_USER"
        locks, phases, actions = _durable_face(app_db)
        assert len(locks) == 1
        assert phases == ["EXPLANATION"]
        assert actions[-1] == "TEACHING_EXPLANATION"


# ---------------------------------------------------------------------------
# 2. the grammar stays closed


def test_an_unknown_control_word_is_a_400_naming_all_five_words(
    tmp_path: Path,
) -> None:
    with web_stack(tmp_path / "app.db") as stack:
        status, data = stack.post("/api/teaching_reply", {"control": "banana"})
        assert status == 400
        for word in ("skip", "attempt", "hint", "reveal", "explanation"):
            assert word in data["error"]
        status, payload = stack.get_json("/api/history")
        assert status == 200
        assert payload["turns"] == []


# ---------------------------------------------------------------------------
# 3. the ro card's last_attempt_feedback


def test_the_ro_card_carries_the_last_attempt_feedback(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    app_db = tmp_path / "app.db"
    with web_stack(
        app_db,
        content_db=pilot_content_db,
        stage=RolloutStage.STUDY_FIRST,
        seed=seed_online,
    ) as stack:
        _open_moment(stack)
        status, payload = stack.get_json("/api/teaching/current")
        assert status == 200
        assert payload["moment"]["last_attempt_feedback"] is None

        status, data = stack.post(
            "/api/teaching_reply",
            {"control": "attempt", "text": ATTEMPT_MISS},
        )
        assert status == 200
        assert data["accepted"] is True
        assert data["feedback"] is not None
        assert "FAILURE" in data["feedback"]

        status, payload = stack.get_json("/api/teaching/current")
        assert status == 200
        assert (
            payload["moment"]["last_attempt_feedback"]
            == "FAILURE（未命中目标表达）"
        )
        # the refresh the field exists for: a second GET reads the same
        status, payload = stack.get_json("/api/teaching/current")
        assert status == 200
        assert (
            payload["moment"]["last_attempt_feedback"]
            == "FAILURE（未命中目标表达）"
        )


# ---------------------------------------------------------------------------
# 4. the face-level mapping


class _RecordingHost:
    """The mapping seam: one canned lock row, a coordinator that records
    the submitted reply request and answers a bare completion (no
    ``reply_text`` attribute — the additive ``delivery_text`` stays
    absent, the W-3 answer shape unchanged)."""

    app_db_path = "stub-app.db"

    def __init__(self, row: tuple[str] | None) -> None:
        self._row = row
        self.submitted: list[Any] = []

    @property
    def db(self) -> "_RecordingHost":
        return self

    def execute(self, _sql: str, _params: Any) -> "_RecordingHost":
        return self

    def fetchone(self) -> tuple[str] | None:
        return self._row

    @property
    def coordinator(self) -> "_RecordingHost":
        return self

    def respond_to_teaching(self, request: Any) -> Any:
        self.submitted.append(request)
        return Ok(
            type("Completion", (), {"moment_state": MomentState.CLOSED})()
        )


def test_the_face_maps_the_help_words_onto_the_runtime_intents() -> None:
    for word, intent in (
        ("hint", TeachingControlIntent.ASK_HINT),
        ("reveal", TeachingControlIntent.ASK_ANSWER),
        ("explanation", TeachingControlIntent.ASK_EXPLANATION),
    ):
        stub = _RecordingHost(row=("AWAITING_USER",))
        answer = _WebFace(stub, str(CONV)).teaching_reply(word)
        (request,) = stub.submitted
        assert request.envelope.control_intent is intent
        assert request.envelope.attempt_present is False
        assert request.envelope.attempt is None
        assert str(request.client_message_id).startswith("web-msg-")
        assert answer == {
            "accepted": True,
            "moment_state": "CLOSED",
            "error": None,
            "feedback": None,
        }

    unknown = _RecordingHost(row=("AWAITING_USER",))
    try:
        _WebFace(unknown, str(CONV)).teaching_reply("banana")
        raised = False
    except ValueError:
        raised = True
    assert raised, "an unknown control word must not silently mean SKIP"
    assert unknown.submitted == []


# ---------------------------------------------------------------------------
# 5. the page's own strings


def test_the_page_pins_the_w6_strings(tmp_path: Path) -> None:
    with web_stack(tmp_path / "app.db") as stack:
        status, _, body = stack.get_raw("/")
        assert status == 200
        page = body.decode("utf-8")
    assert "批改中…" in page
    assert 'helpButton("看提示", "hint"' in page
    assert 'helpButton("看答案", "reveal"' in page
    assert 'helpButton("解释", "explanation"' in page
    assert "看答案将结束本题并显示完整形式，确定？" in page
    assert "setReplyBusy(" in page
    assert "showResultStrip(" in page
    assert "提交失败，请重试" in page
    assert "last_attempt_feedback" in page
    # the card stays XSS-inert: textContent, never innerHTML
    assert "textContent" in page
    assert ".innerHTML" not in page
