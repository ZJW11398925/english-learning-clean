"""v3-1 — the teaching card's IA redo (P0-2) and the PARTIAL guide (A3),
pinned at the two faces the card actually has:

1. **the online chain** (the P0-1 main scenario end to end): a learner
   error opens the i-think moment through the real dispatch, the
   rewritten key judges the depends-sentence PARTIAL with the moment
   still ``AWAITING_USER`` (可再答), the reply face carries the additive
   ``delivery_kind`` (HINT / REVEAL / RETRY) the card routes on, and the
   guided retry closes with SUCCESS;
2. **the card's source** (components.js / components.css, the rd-4/v21
   pinning style): the result strip and the attempt line are slots
   (replace, never append), the skip rides its own disarming row
   (至多一枚), the reference answer is its own labelled block that never
   mixes into the letter body, older help deliveries fold away, and the
   PARTIAL guide line exists and leaves with the PARTIAL.

The card stays XSS-inert: every word rides textContent (the cs-0/W-6
discipline, asserted again below).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from elc.platform.types import EvidenceModality, TargetId
from elc.teaching.rollout import RolloutStage
from tests.host import test_w1_web
from tests.host.test_w1_web import (
    _WebFace,
    web_stack,
)

#: The W-1 suite's module-scoped pilot ``content.db`` fixture, bound under
#: the same name so pytest resolves it for this module's tests too.
pilot_content_db = test_w1_web.pilot_content_db

#: The i-think trigger (pilot rule ordinal 0, SUBJECT_OMISSION): the same
#: shape the detection fixtures pin.
I_THINK_ERROR_TEXT = "Think we should take the earlier train and skip the rush."
#: The dogfood P0-1 attempt: semantically correct, formula present, not
#: the canonical sentence.
DEPENDS_ATTEMPT = "I think it depends on the weather."
CANONICAL_ATTEMPT = "I think it is going to rain."

WEBUI = Path(test_w1_web.__file__).parents[2] / "src" / "elc" / "webui"


def _seed_with_i_think(host: Any) -> None:
    """``seed_online`` plus the §5.2 row for the P0-1 target: the real
    ``elc seed`` writes one row per EV target, so a moment on i-think
    needs its own schedulable row (the seed_online_and_second_target
    shape)."""

    test_w1_web.seed_online(host)
    row = host.curriculum.get_target(TargetId("res-hedge-i-think"))
    assert row.__class__.__name__ == "Ok", row
    scheduled = host.scheduler.recompute_schedule_item(
        row.value.target_type,
        TargetId("res-hedge-i-think"),
        EvidenceModality(row.value.evidence_modality),
        datetime.now(tz=UTC).isoformat(),
    )
    assert scheduled.__class__.__name__ == "Ok", scheduled


def _text(name: str) -> str:
    return (WEBUI / name).read_text(encoding="utf-8")


def _fn_body(source: str, name: str) -> str:
    """One top-level function's body, for the rd-4 style scoped asserts
    (``async function`` tails included)."""
    start = source.index(f"function {name}(")
    ends = [
        at
        for at in (
            source.find("\nfunction ", start + 1),
            source.find("\nasync function ", start + 1),
        )
        if at != -1
    ]
    return source[start : min(ends)]


# ---------------------------------------------------------------------------
# 1. the P0-1 main scenario, end to end over the online chain


def test_the_p01_scenario_judges_partial_and_stays_answerable(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    app_db = tmp_path / "app.db"
    with web_stack(
        app_db,
        content_db=pilot_content_db,
        stage=RolloutStage.STUDY_FIRST,
        seed=_seed_with_i_think,
    ) as stack:
        status, data = stack.post("/api/turn", {"text": I_THINK_ERROR_TEXT})
        assert status == 200
        (moment,) = data["teaching_moments"]
        assert moment["focus_target_id"] == "res-hedge-i-think"
        assert moment["lifecycle_state"] == "AWAITING_USER"

        # the P0-1 attempt: PARTIAL, the moment stays answerable
        status, data = stack.post(
            "/api/teaching_reply",
            {"control": "attempt", "text": DEPENDS_ATTEMPT},
        )
        assert status == 200
        assert data["accepted"] is True
        assert data["feedback"] == "PARTIAL（部分正确）"
        assert data["moment_state"] == "AWAITING_USER"
        # the miss delivers the runtime's own retry line, kind-labelled
        # (the test stack's scripted provider prefixes its canned turn
        # words — the pinned fact is the runtime's fixed line at the tail)
        assert data["delivery_text"].endswith("这句还没说对——再试一回。")
        assert data["delivery_kind"] == "RETRY"

        # a help arm is kind-labelled too: the hint is a HINT, the answer
        # a REVEAL (the seam the card's reference-answer block routes on)
        status, data = stack.post("/api/teaching_reply", {"control": "hint"})
        assert status == 200
        assert data["accepted"] is True
        assert data["delivery_kind"] == "HINT"
        status, data = stack.post("/api/teaching_reply", {"control": "reveal"})
        assert status == 200
        assert data["accepted"] is True
        assert data["delivery_kind"] == "REVEAL"
        assert data["delivery_text"].endswith(CANONICAL_ATTEMPT)

        # the guided retry: the canonical sentence closes with SUCCESS
        status, data = stack.post(
            "/api/teaching_reply",
            {"control": "attempt", "text": CANONICAL_ATTEMPT},
        )
        assert status == 200
        assert data["feedback"] == "SUCCESS（回答正确）"
        assert data["moment_state"] == "CLOSED"

        # the durable face keeps the newest verdict readable (W-6's ro
        # field, still the refresh's source)
        status, payload = stack.get_json("/api/teaching/current")
        assert status == 200
        assert payload["moment"] is None


def test_the_attemptless_words_stay_additive_shaped() -> None:
    """The additive rule's shape: no delivery → no ``delivery_text`` and
    no ``delivery_kind`` key (the W-6 exact answer shape is unchanged)."""

    lock_row: tuple[str] | None = ("AWAITING_USER",)

    class _Stub:
        app_db_path = "stub-app.db"
        submitted: list[Any] = []

        @property
        def db(self) -> "_Stub":
            return self

        def execute(self, _sql: str, _params: Any) -> "_Stub":
            return self

        def fetchone(self) -> tuple[str] | None:
            return lock_row

        @property
        def coordinator(self) -> "_Stub":
            return self

        def respond_to_teaching(self, request: Any) -> Any:
            self.submitted.append(request)
            from elc.platform.types import Ok
            from elc.teaching.types import MomentState

            return Ok(
                type("Completion", (), {"moment_state": MomentState.CLOSED})()
            )

    stub = _Stub()
    answer = _WebFace(stub, "conv-x").teaching_reply("skip")
    assert answer == {
        "accepted": True,
        "moment_state": "CLOSED",
        "error": None,
        "feedback": None,
    }
    assert "delivery_text" not in answer
    assert "delivery_kind" not in answer


# ---------------------------------------------------------------------------
# 2. the card's source: slots replace, the answer block stands alone


def test_the_result_strip_and_attempt_line_are_slots() -> None:
    """P0-2 ①③（append 回潮负控）：结果条与回试行都是「查旧 → 原位改写」
    的槽位件——showResultStrip 不再无条件 createElement，readReplyAnswer
    不再 append <br>/<b> 行。"""

    js = _text("components.js")
    strip_body = _fn_body(js, "showResultStrip")
    assert 'card.querySelector(".resultstrip")' in strip_body
    assert 'if (!strip) {' in strip_body
    # the old append-always shape is gone repo-wide
    assert 'const strip = document.createElement("div");' not in js
    reply_body = _fn_body(js, "readReplyAnswer")
    assert 'card.querySelector(".note-state")' in reply_body
    assert 'document.createElement("br")' not in reply_body
    assert 'const b = document.createElement("b");' not in reply_body
    assert 'state.className = "note-state";' in reply_body


def test_the_skip_rides_its_own_disarming_row() -> None:
    """P0-2 ②（漏拆负控）：「先搁着」挂在 .skiprow 拆装组里，
    disarmMomentCard 一并拆——多轮后卡内至多一枚。"""

    js = _text("components.js")
    controls_body = _fn_body(js, "addReplyControls")
    assert 'skiprow.className = "skiprow";' in controls_body
    # the button is appended to the row, never to the card directly
    assert "skiprow.appendChild(skip);" in controls_body
    assert "card.appendChild(skip);" not in js
    disarm_body = _fn_body(js, "disarmMomentCard")
    assert 'card.querySelectorAll(".skiprow")' in disarm_body
    assert "row.remove();" in disarm_body
    css = _text("components.css")
    assert ".skiprow { margin-top: 10px; }" in css


def test_the_reference_answer_is_its_own_labelled_block() -> None:
    """B3（混排回潮负控）：REVEAL 走 .note-answer 独立区块——「参考答案」
    标签打头；交付文本永不进信流（cs-0 契约 + v3-1 分派）。"""

    js = _text("components.js")
    delivery_body = _fn_body(js, "noteDelivery")
    assert 'kind === "REVEAL"' in delivery_body
    assert 'block.className = "note-answer";' in delivery_body
    assert 'tag.textContent = "参考答案";' in delivery_body
    # the letter flow never carries a delivery: the only addLine calls are
    # the failure line and the system receipt
    assert 'addLine("system", data.delivery_text' not in js
    assert 'addLine("assistant"' not in js
    # the cs-0 contract line survives (the newest delivery is a .noteline)
    assert 'note.className = "noteline";' in js
    css = _text("components.css")
    assert ".note-answer {" in css
    assert "border-left: 2px solid var(--pencil);" in css


def test_older_deliveries_fold_into_a_details_history() -> None:
    """B4：最新交付显式，更早的收进 <details class="note-history"> 折叠
    （组头带计数）；折叠是纯前端态（零新端点字面）。"""

    js = _text("components.js")
    delivery_body = _fn_body(js, "noteDelivery")
    assert 'history = document.createElement("details");' in delivery_body
    assert 'history.className = "note-history";' in delivery_body
    assert "已看过的提示与讲解" in js
    css = _text("components.css")
    assert ".note-history {" in css
    assert ".note-history summary {" in css


def test_the_partial_guide_line_exists_and_leaves_with_the_partial() -> None:
    """A3：◐ 结果条在场时伴一条方向指引（绑「提示」词族），至多一条，
    PARTIAL 退场即摘；FAILURE/SUCCESS 判词映射保持既有定稿。"""

    js = _text("components.js")
    assert 'line.className = "partialguide";' in js
    assert "答了一半——目标表达已经在句子里了，把整句说完，或点「提示」再看一眼。" in js
    guide_body = _fn_body(js, "showPartialGuide")
    assert "if (!on) {" in guide_body
    assert "line.remove();" in guide_body
    strip_body = _fn_body(js, "showResultStrip")
    assert 'showPartialGuide(card, strip, symbol === "◐");' in strip_body
    reply_body = _fn_body(js, "readReplyAnswer")
    assert 'showPartialGuide(card, null, false);' in reply_body
    css = _text("components.css")
    assert ".partialguide {" in css
    # the verdict family itself is untouched (rd-2 定稿)
    assert 'PARTIAL: "◐ 答了一半",' in js
    assert 'FAILURE: "✗ 没答中",' in js


def test_the_card_stays_xss_inert() -> None:
    """The cs-0/W-6 discipline on the new faces: textContent everywhere,
    innerHTML nowhere."""

    js = _text("components.js")
    assert ".innerHTML" not in js
    for word in ("参考答案", "已看过的提示与讲解", "答了一半"):
        assert word in js
