"""F-2 — the feature faces (功能面): the 学习 view, teach-me, the blocked line.

The server, the host and the online seed are the W-1 suite's own fixtures
(one serving stack, one production assembly); this file pins only the F-2
face on top of F-1's shell:

1. the 学习 view — a third tab and its panels (R-1R：可教目标 52 行迁往
   今日 · 可以练的表达，本页留 复习日程 / 学习目标 / 证据记录 原值于
   折叠的原始读数区), the 「教我这一句」 act, all ``textContent``-only;
2. ``GET /api/learning`` — the diagnostics construction repeated: read-only
   SQL on the work queue, panel-level guards, honest empty shapes, and the
   read-silence pin (a content snapshot, so UPDATE-class mutations fail it
   too);
3. ``GET /api/targets`` — the corpus truth: with a content leg the
   readiness R3+ set (today 52 R4 targets, an R1 target excluded by name);
   without one the ``schedule_item`` fallback under the ``schedule_item``
   source word;
4. ``POST /api/teach_me`` — the full user-initiated teaching chain through
   the coordinator's own ``request_teaching`` (survey fact this suite pins
   end to end: one call opens the moment at ``AWAITING_USER`` — the P3-1B
   opening delivery happens inside the entry), the attempt → judgement →
   closure loop over the opened moment, the honest refusal arms (lock
   conflict, unknown target) and the 400 grammar arms;
5. the blocked line — the chat view's one gray honest sentence after a
   turn that taught nothing, gated on exactly that condition in the page
   source, with the diagnostics data the line reads proven to exist over
   the real chain.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from elc.teaching.rollout import RolloutStage
from elc.web import _WebFace
from tests.host import test_w1_web
from tests.host.test_w1_web import (
    ATTEMPT_HIT,
    ATTEMPT_MISS,
    CONV,
    ERROR_TEXT,
    EV_TARGET,
    _page_source,
    seed_online,
    web_stack,
)

#: The W-1 suite's module-scoped pilot ``content.db`` fixture, bound under
#: the same name so pytest resolves it for this module's tests too.
pilot_content_db = test_w1_web.pilot_content_db

#: The corpus truth the readiness face serves today (the C3-d calibration
#: endpoint): 52 targets at R4, the only words at or above the R3 floor.
READINESS_R3_PLUS_COUNT = 52

#: A corpus target at R1 — declared, but below the teachable floor, so it
#: must never appear in the R3+ list.
R1_TARGET = "res-colloc-come-to-a-conclusion"

#: The schedule panel's exact column face (the migration's own words, the
#: eight columns the task names).
SCHEDULE_ITEM_KEYS = (
    "target_type",
    "target_id",
    "review_state",
    "review_urgency",
    "next_review_window_start",
    "next_review_window_end",
    "spacing_stage",
    "updated_at",
)


def _seed_schedule_row(host: Any) -> None:
    """One ``schedule_item`` row, written directly — the prep-1 tier's
    fallback source needs no controller, only the durable row."""

    _seed_schedule_rows(host, EV_TARGET)


def _seed_schedule_rows(host: Any, *target_ids: str) -> None:
    """One ``schedule_item`` row per named target, written directly (the
    prep-1 tier holds no scheduler controller, only the durable table the
    fallback face and the schedule panel read)."""

    for index, target_id in enumerate(target_ids):
        host.db.execute(
            "INSERT INTO schedule_item (schedule_item_id, target_type,"
            " target_id, evidence_modality, review_state, review_urgency,"
            " next_review_window_start, next_review_window_end,"
            " spacing_stage, source_learning_watermark, version, updated_at)"
            f" VALUES ('si-f2-{index}', 'RESOURCE', ?, 'TEXT_PRODUCTION',"
            " 'UPCOMING', 0.5, '2026-09-29T08:00:00+00:00',"
            " '2026-09-29T09:00:00+00:00', NULL, 'wm-f2', 'v1',"
            " '2026-09-28T08:00:00+00:00')",
            (target_id,),
        )
    host.db.commit()


class _FaceHost:
    """Just enough host for the learning face: one plain sqlite
    connection, nothing else (the F-1 diagnostics stub's shape)."""

    app_db_path = "stub-app.db"

    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db

    @property
    def db(self) -> sqlite3.Connection:
        return self._db


# ---------------------------------------------------------------------------
# 1. the 学习 view — the page's third tab and its faces


def test_the_page_has_the_learning_view(tmp_path: Path) -> None:
    page_source = _page_of(tmp_path)
    # the 学习 block: R-1 随迁——常挂学案·进步，setlinks 的 data-block
    # 链接退役（缺位钉；p-3 先例）；R-1R 随迁（⑧ 8.2.5）：「可教目标」
    # 52 行从记录页移除（唯一居所 = 今日 · 可以练的表达，缺位钉），
    # 日程/目标/证据三面原值迁入页底「原始读数」折叠区（id 保留），
    # 刷新钮全退（进节即拉，learning-refresh 缺位钉）
    assert 'data-block="learning"' not in page_source
    assert ">学习</button>" not in page_source
    assert 'id="set-learning"' in page_source
    # the three raw panels keep their ids inside the 原始读数 fold; the
    # 52-row target list and the refresh button are gone
    for element in (
        "learn-schedule",
        "learn-goals",
        "learn-evidence",
    ):
        assert f'id="{element}"' in page_source
    assert 'id="target-list"' not in page_source
    assert 'id="learning-refresh"' not in page_source
    # the raw panel labels, in the task's own words（原值区合法形态）
    for label in ("复习日程", "学习目标", "证据记录"):
        assert label in page_source
    assert "可教目标" not in page_source
    # the one read, the one act, and the show/hide branch
    assert '"/api/learning"' in page_source
    assert '"/api/targets"' in page_source
    assert '"/api/teach_me"' in page_source
    assert "loadTargets" not in page_source
    assert "loadLearning" in page_source
    # p-2 migrated the literal, R-1 migrated the mechanism: the four-block
    # loop's `hidden = name !== block` became the section switch's
    # `hidden = key !== name` (一节可见 semantics unchanged — the pin
    # moved, not deleted)
    assert 'key !== name' in page_source
    # the 教我 act: click-through, no confirm (a low-risk request)——R-1R
    # 随迁：钮词「教我这一句」（⑧ 8.2.3 线框定稿），库外类 .teach-me 不变
    assert "教我这一句" in page_source
    assert "教我这个" not in page_source
    assert 'button.className = "teach-me";' in page_source
    # the XSS face: the target name rides textContent, never markup
    # (p-1 随迁：行工厂 teachRow 被今日屏到期块与可以练的表达共用，
    # 名字经 b.textContent = name 落节点——语义不变，形状随迁)
    assert "b.textContent = name;" in page_source


def _page_of(tmp_path: Path) -> str:
    """The served page source, over the plain offline stack — the F-G1
    union: the shell plus every static asset it links."""

    with web_stack(tmp_path / "app.db") as stack:
        return _page_source(stack)


# ---------------------------------------------------------------------------
# 2. GET /api/learning — the three panels


def test_learning_serves_the_three_panels(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """Over the seeded online chain: the schedule row the seed wrote, the
    goal portfolio parsed as the JSON it was written as, and the honest
    empty evidence panel — no claim judged yet, zero counts, no invented
    row."""

    with web_stack(
        tmp_path / "app.db",
        content_db=pilot_content_db,
        stage=RolloutStage.STUDY_FIRST,
        seed=seed_online,
    ) as stack:
        status, data = stack.get_json("/api/learning")
        assert status == 200
        assert set(data) == {"schedule", "goals", "evidence"}
        for panel in data.values():
            assert "error" not in panel

        schedule = data["schedule"]
        assert schedule["items"], "the seed wrote one schedule row"
        row = next(
            item
            for item in schedule["items"]
            if item["target_id"] == EV_TARGET
        )
        assert set(row) == set(SCHEDULE_ITEM_KEYS)
        assert row["target_type"] == "RESOURCE"
        assert row["review_state"] == "NOT_SCHEDULED"
        assert row["review_urgency"] == 0.0
        assert row["next_review_window_start"] is None
        assert row["next_review_window_end"] is None

        goals = data["goals"]
        assert goals["portfolios"], "the seed wrote one portfolio"
        portfolio = goals["portfolios"][0]
        # the seed keys the portfolio by the Local V1 user's own scope word
        assert portfolio["goal_portfolio_id"] == "user-local-v1"
        goal_list = portfolio["goals"]
        assert isinstance(goal_list, list)
        assert goal_list[0]["goal_id"] == "goal-w1"
        assert portfolio["modality_weights"] == {"SPEAKING": 1.0}

        evidence = data["evidence"]
        assert evidence["claims"] == []
        assert evidence["evidence_claim_count"] == 0
        assert evidence["learner_target_state_count"] == 0


def test_the_learning_panels_survive_a_dirty_database() -> None:
    """A database without the tables answers ``{"error": …}`` in each
    panel's own slot — never a 500 for the whole readout."""

    face = _WebFace(_FaceHost(sqlite3.connect(":memory:")), str(CONV))  # type: ignore[arg-type]
    data = face.learning()
    assert set(data) == {"schedule", "goals", "evidence"}
    for panel in data.values():
        assert set(panel) == {"error"}
        assert "OperationalError" in panel["error"]


def test_the_learning_face_is_read_only(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """Learning and targets GETs over a chain that really taught: every
    key table's full content stays exactly where the turn left it — the
    F-1 content-snapshot shape, so an UPDATE-class mutation inside a
    panel fails the pin just the same."""

    app_db = tmp_path / "app.db"
    tables = (
        "schedule_item",
        "review_event",
        "goal_portfolio",
        "evidence_claim",
        "learner_target_state",
        "teaching_moment",
        "active_teaching_lock",
    )

    def snapshot() -> dict[str, list]:
        ro = sqlite3.connect(f"file:{app_db}?mode=ro", uri=True)
        try:
            return {
                table: ro.execute(
                    f"SELECT * FROM {table} ORDER BY rowid"
                ).fetchall()
                for table in tables
            }
        finally:
            ro.close()

    with web_stack(
        app_db,
        content_db=pilot_content_db,
        stage=RolloutStage.STUDY_FIRST,
        seed=seed_online,
    ) as stack:
        status, data = stack.post("/api/turn", {"text": ERROR_TEXT})
        assert status == 200
        assert data["teaching_moments"]
        before = snapshot()
        for _ in range(3):
            status, learning = stack.get_json("/api/learning")
            assert status == 200
            assert "error" not in learning["schedule"]
            status, targets = stack.get_json("/api/targets")
            assert status == 200
            assert targets["targets"]
        assert snapshot() == before


# ---------------------------------------------------------------------------
# 3. GET /api/targets — the teachable corpus


def test_targets_lists_the_readiness_r3_corpus(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """With a content leg the readiness table is the source: today's
    corpus answers 52 targets (all R4), the named R1 target is excluded,
    and every entry is the ``{target_id, name}`` pair with the id's
    spoken name."""

    with web_stack(
        tmp_path / "app.db",
        content_db=pilot_content_db,
        stage=RolloutStage.STUDY_FIRST,
        seed=seed_online,
    ) as stack:
        status, data = stack.get_json("/api/targets")
        assert status == 200
        assert data["source"] == "readiness>=R3"
        entries = data["targets"]
        assert len(entries) == READINESS_R3_PLUS_COUNT
        ids = [entry["target_id"] for entry in entries]
        assert len(set(ids)) == len(ids)
        assert EV_TARGET in ids
        assert R1_TARGET not in ids
        for entry in entries:
            assert set(entry) == {"target_id", "name"}
            assert entry["name"]
        by_id = {entry["target_id"]: entry["name"] for entry in entries}
        assert by_id[EV_TARGET] == "anyway"


def test_targets_without_content_face_names_the_schedule_set(
    tmp_path: Path,
) -> None:
    """The prep-1 tier holds no readiness face: the fallback is the
    ``schedule_item`` target set, and the ``source`` word says so —
    schedule 覆盖的供给目标, never an invented corpus."""

    with web_stack(tmp_path / "app.db", seed=_seed_schedule_row) as stack:
        status, data = stack.get_json("/api/targets")
        assert status == 200
        assert data["source"] == "schedule_item"
        assert data["targets"] == [
            {"target_id": EV_TARGET, "name": "anyway"}
        ]


def test_the_schedule_panel_orders_due_first(tmp_path: Path) -> None:
    """The panel's reading order: DUE first, UPCOMING next, NOT_SCHEDULED
    last — the order a person reads the list in, not the rowid order."""

    def seed_three_states(host: Any) -> None:
        # inserted NOT_SCHEDULED first, so rowid order differs from the
        # panel's reading order and only the CASE ordering can pass
        for state in ("NOT_SCHEDULED", "DUE", "UPCOMING"):
            host.db.execute(
                "INSERT INTO schedule_item (schedule_item_id, target_type,"
                " target_id, evidence_modality, review_state, review_urgency,"
                " next_review_window_start, next_review_window_end,"
                " spacing_stage, source_learning_watermark, version,"
                " updated_at)"
                " VALUES (?, 'RESOURCE', ?, 'TEXT_PRODUCTION', ?, 1.0,"
                " NULL, NULL, NULL, 'wm-f2', 'v1',"
                " '2026-09-28T08:00:00+00:00')",
                (f"si-f2-{state}", f"res-order-{state}", state),
            )
        host.db.commit()

    with web_stack(tmp_path / "app.db", seed=seed_three_states) as stack:
        status, data = stack.get_json("/api/learning")
        assert status == 200
        items = data["schedule"]["items"]
        assert [item["review_state"] for item in items] == [
            "DUE",
            "UPCOMING",
            "NOT_SCHEDULED",
        ]


# ---------------------------------------------------------------------------
# 4. POST /api/teach_me — the whole chain in one call


def test_teach_me_opens_answers_and_closes(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """The user-initiated teaching loop, end to end over the real chain:
    the request opens the moment at AWAITING_USER (the opening delivery
    happened inside the entry), the card is readable on the W-4 poll
    face, a second target's request is refused by the runtime's own
    lock, and the miss-then-hit attempt pair re-prompts then closes —
    after which the lock is gone."""

    with web_stack(
        tmp_path / "app.db",
        content_db=pilot_content_db,
        stage=RolloutStage.STUDY_FIRST,
        seed=seed_online,
    ) as stack:
        status, targets = stack.get_json("/api/targets")
        assert status == 200
        ids = [entry["target_id"] for entry in targets["targets"]]
        assert EV_TARGET in ids
        other = next(target for target in ids if target != EV_TARGET)

        status, opened = stack.post("/api/teach_me", {"target_id": EV_TARGET})
        assert status == 200
        assert opened["accepted"] is True
        assert opened["error"] is None
        assert opened["moment"]["focus_target_id"] == EV_TARGET
        assert opened["moment"]["lifecycle_state"] == "AWAITING_USER"

        # the W-4 poll face reads the same moment off the ro route
        status, current = stack.get_json("/api/teaching/current")
        assert status == 200
        assert current["moment"] is not None
        assert current["moment"]["focus_target_id"] == EV_TARGET
        assert current["moment"]["lifecycle_state"] == "AWAITING_USER"

        # the runtime refuses a second open itself — honest pass-through
        status, second = stack.post("/api/teach_me", {"target_id": other})
        assert status == 200
        assert second["accepted"] is False
        assert "TEACHING_LOCK_CONFLICT" in second["error"]

        # the attempt loop: miss re-prompts, hit closes and releases
        status, miss = stack.post(
            "/api/teaching_reply",
            {"control": "attempt", "text": ATTEMPT_MISS},
        )
        assert status == 200
        assert miss["accepted"] is True
        assert miss["moment_state"] == "AWAITING_USER"
        assert miss["feedback"] is not None
        assert miss["feedback"].startswith("FAILURE")

        status, hit = stack.post(
            "/api/teaching_reply",
            {"control": "attempt", "text": ATTEMPT_HIT},
        )
        assert status == 200
        assert hit["accepted"] is True
        assert hit["moment_state"] != "AWAITING_USER"
        assert hit["feedback"] is not None
        assert hit["feedback"].startswith("SUCCESS")

        status, current = stack.get_json("/api/teaching/current")
        assert status == 200
        assert current["moment"] is None


def test_teach_me_honest_refusals_and_grammar(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """An unknown target is the runtime's own deterministic DENY (200 +
    accepted: false + the reason), and a body outside the
    ``{"target_id": …}`` grammar is a 400 — four arms."""

    with web_stack(
        tmp_path / "app.db",
        content_db=pilot_content_db,
        stage=RolloutStage.STUDY_FIRST,
        seed=seed_online,
    ) as stack:
        status, refused = stack.post(
            "/api/teach_me", {"target_id": "res-does-not-exist"}
        )
        assert status == 200
        assert refused["accepted"] is False
        assert "TARGET_INVALID" in refused["error"]
        assert refused["moment"] is None

        for bad in (
            b"not json at all",
            b"{}",
            b'{"target_id": ""}',
            b'{"target_id": "   "}',
        ):
            status, answer = stack.post_raw("/api/teach_me", bad)
            assert status == 400, bad
            assert "target_id" in answer["error"]


# ---------------------------------------------------------------------------
# 5. the blocked line — one honest gray sentence after a quiet turn


def test_the_blocked_line_is_pinned_in_the_page(tmp_path: Path) -> None:
    page_source = _page_of(tmp_path)
    # the gate is exactly "the turn taught nothing" — the mutation that
    # makes the line always show must delete this line to do it
    assert "if (!moments.length) showBlockedNote();" in page_source
    # the line reads the diagnostics face and dies silently on failure
    assert "async function showBlockedNote()" in page_source
    assert "if (!panel || panel.error) return;" in page_source
    # R-1R 随迁（⑧ 8.2.2 定稿）：blocked 行两形——分量不足（候选名
    # todayName 派生 + 「原委在 学案 · 记录」链接）/ 被门规拦（中文
    # 理由）；全键与浮点不再进信流
    assert "这一轮没有递短笺——客厅想过「" in page_source
    assert "今天它的分量还不够。（原委在 " in page_source
    assert "这一轮没有递短笺——被门规拦下（" in page_source
    assert "本轮未教学" not in page_source
    assert "低于阈值" not in page_source
    # the gray small-text face and its inert rendering
    assert ".blockedline" in page_source
    assert 'line.className = "blockedline";' in page_source


def test_the_blocked_line_has_data_after_a_blocked_turn(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """The data path the line reads, over the real chain: a second
    error-text turn while the first moment still holds the lock teaches
    nothing (the branch the page JS gates on) and the diagnostics
    face carries the why-not facts — a silenced candidate or the gate's
    DENY codes — so the line has something honest to say."""

    with web_stack(
        tmp_path / "app.db",
        content_db=pilot_content_db,
        stage=RolloutStage.STUDY_FIRST,
        seed=seed_online,
    ) as stack:
        status, first = stack.post("/api/turn", {"text": ERROR_TEXT})
        assert status == 200
        assert first["teaching_moments"]
        status, skipped = stack.post(
            "/api/teaching_reply", {"control": "skip"}
        )
        assert status == 200
        assert skipped["accepted"] is True

        status, second = stack.post("/api/turn", {"text": ERROR_TEXT})
        assert status == 200
        assert second["teaching_moments"] == []

        status, diag = stack.get_json("/api/diagnostics")
        assert status == 200
        why_not = diag["why_not_teach"]
        assert why_not["created_at"] is not None
        assert why_not["candidates"] or why_not["gate_deny"]

        # the 学习 read rides the same turn: nothing here broke it
        status, learning = stack.get_json("/api/learning")
        assert status == 200
        assert "error" not in learning["evidence"]


def test_the_evidence_panel_shows_data_after_a_closed_loop(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """Review LOW-1: the evidence panel had only its honest-empty pin —
    a teaching loop that really closed (a judged miss then a judged hit)
    must leave the panel carrying the claims, newest first, not just the
    empty shape."""

    with web_stack(
        tmp_path / "app.db",
        content_db=pilot_content_db,
        stage=RolloutStage.STUDY_FIRST,
        seed=seed_online,
    ) as stack:
        status, opened = stack.post("/api/teach_me", {"target_id": EV_TARGET})
        assert status == 200
        assert opened["accepted"] is True

        for text in (ATTEMPT_MISS, ATTEMPT_HIT):
            status, reply = stack.post(
                "/api/teaching_reply", {"control": "attempt", "text": text}
            )
            assert status == 200
            assert reply["accepted"] is True

        status, learning = stack.get_json("/api/learning")
        assert status == 200
        evidence = learning["evidence"]
        assert "error" not in evidence
        assert evidence["evidence_claim_count"] >= 2
        assert evidence["claims"], "a closed loop must leave claims shown"
        shown = evidence["claims"]
        assert all(claim["target_id"] == EV_TARGET for claim in shown)
        # newest first: the hit's claim is not older than the miss's
        assert shown[0]["created_at"] >= shown[-1]["created_at"]
