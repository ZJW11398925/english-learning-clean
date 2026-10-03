"""主线-2 — 调度与历史纵深：三面一刀的钉面（tests/host 新钉）。

对 ``VAL-OPI-32409938-…12`` 五组的可执行钉（组⑤变异组的运行留痕在回执，
仓外变异场承载——本文件落的是变异组要打红的那些钉本身）：

1. 组① 调度三态（``GET /api/schedule``）：调度腿没装配 = ``available:
   false`` 的诚实空态（不虚构）；有腿无行 = 三桶全空的诚实空态；有行 =
   Scheduler 自己的分档视图（DUE/OVERDUE/UPCOMING 各归其桶，行字段
   原值直出，无窗口行不进任何桶——视图自己的成员规则）。
2. 组② 全历史参数（``GET /api/history``）：窗口默认语义不变（不带参数
   仍恰好 50 轮）+ ``?limit=n`` / ``?full=1`` 显式宽度 + 诚实分页位
   ``has_more`` + fail-closed 文法（两参数互斥、非法值 400 人话）。
3. 组③ 跨信足迹（``GET /api/target_footprint?id=``）：ACTIVE-only 聚合
   （SUPERSEDED/INVALIDATED 不算足迹——§18）、按轮分布与轮次序数、
   逐轮判分原值、无证据 ``found:false`` 的 200 事实、缺 ``?id`` 400。
4. 组④ 随迁扫全：页源（shell + 六资产）与 web 源的口径句/入口/路由
   零残留（旧「最近 50 轮」信档句与「跨信重现不做」退役有钉；spec 的
   9.12-23④ 缝闭合句在场）。

服务栈与在线种子沿用 W-1 套件的既有 fixture（one serving stack, one
production assembly）；证据行经真 CP0 轮次落（FK ON——无孤儿可造）。
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.error import HTTPError

from elc.platform.types import Ok
from elc.web import HISTORY_TURNS, _commit
from tests.host import test_w1_web
from tests.host.test_w1_web import CONV, _page_source, web_stack

#: The W-1 suite's module-scoped pilot ``content.db`` fixture, bound under
#: the same name so pytest resolves it for this module's tests too.
pilot_content_db = test_w1_web.pilot_content_db

#: The default-window semantic nail's own number (the constant is the
#: server's; the pin reads it so the nail and the face can never drift
#: apart silently).
DEFAULT_WINDOW = HISTORY_TURNS


def _get_status_json(stack: Any, path: str) -> tuple[int, Any]:
    """GET that answers error statuses as data — the grammar arms (and the
    missing-``?id`` arm) ride HTTP 400 with a JSON body, and ``urllib``
    turns those into exceptions the happy-path helper does not catch."""

    try:
        return stack.get_json(path)
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# seeds — all on the worker thread (the web_stack contract)


def _seed_bare_turns(host: Any, count: int) -> list[str]:
    """``count`` real CP0 user turns (no assistant side) — the pagination
    seeds. Returns the turn ids in commit order (durable sequence order)."""

    turn_ids: list[str] = []
    for index in range(count):
        committed = host.conversations.commit_user_turn(
            _commit(CONV, f"ml2 seed line {index}")
        )
        assert isinstance(committed, Ok), committed
        turn_ids.append(str(committed.value.turn_id))
    return turn_ids


def _seed_evidence_group(
    host: Any, group_id: str, turn_id: str, created_at: str
) -> None:
    host.db.execute(
        "INSERT INTO evidence_group (evidence_group_id, source_turn_id,"
        " conversation_id, evidence_modality, created_at)"
        " VALUES (?, ?, ?, 'TEXT_PRODUCTION', ?)",
        (group_id, turn_id, str(CONV), created_at),
    )


def _seed_claim(
    host: Any,
    *,
    claim_id: str,
    group_id: str,
    target_id: str,
    turn_id: str,
    outcome: str,
    status: str,
    created_at: str,
) -> None:
    """One ``evidence_claim`` row (migration 0004's columns, the NOT NULL
    set filled with the ledger's own vocabulary) — the footprint seeds."""

    host.db.execute(
        "INSERT INTO evidence_claim (evidence_claim_id, evidence_group_id,"
        " target_type, target_id, performance_type, polarity, outcome,"
        " qualifiers, evidence_modality, elicitation_type, spontaneity,"
        " support_level, answer_exposure_state, context_novelty,"
        " persona_novelty, evidence_modality_novelty,"
        " support_attribution_certainty, support_attribution_basis,"
        " evaluator_id, evaluator_version, evaluator_confidence, status,"
        " source_turn_id, conversation_id, created_at)"
        " VALUES (?, ?, 'RESOURCE', ?, 'INDEPENDENT_PRODUCTION',"
        " 'POSITIVE', ?, '[]', 'TEXT_PRODUCTION', 'NATURAL',"
        " 'SPONTANEOUS', 'NONE', 'UNSEEN', 0.0, 0.0, 0.0, 1.0, 'self',"
        " 'ml2-evaluator', 'v1', 0.9, ?, ?, ?, ?)",
        (
            claim_id,
            group_id,
            target_id,
            outcome,
            status,
            turn_id,
            str(CONV),
            created_at,
        ),
    )


def _seed_schedule_row(
    host: Any,
    *,
    item_id: str,
    target_id: str,
    review_state: str,
    spacing_stage: str | None,
    window_start: str | None,
    window_end: str | None,
) -> None:
    """One ``schedule_item`` row written directly (the F-2 precedent: the
    durable row is the seed; the view under test classifies it). The stored
    ``review_state`` is written coherent with the row's own window — the
    reading a real ``recompute_schedule_item`` would have left — so the
    verbatim pass-through pins stay consistent with the classification."""

    host.db.execute(
        "INSERT INTO schedule_item (schedule_item_id, target_type,"
        " target_id, evidence_modality, review_state, review_urgency,"
        " next_review_window_start, next_review_window_end,"
        " spacing_stage, source_learning_watermark, version, updated_at)"
        " VALUES (?, 'RESOURCE', ?, 'TEXT_PRODUCTION', ?, NULL,"
        " ?, ?, ?, 'wm-ml2', 'v1', '2026-10-03T00:00:00+00:00')",
        (
            item_id,
            target_id,
            review_state,
            window_start,
            window_end,
            spacing_stage,
        ),
    )


def _seed_windowed_schedule(host: Any) -> None:
    """The classification seeds: one row per bucket word plus one row with
    no window (NOT_SCHEDULED — no bucket), windows built around the real
    now so the view's own ``state_at`` decides the buckets."""

    now = datetime.now(tz=UTC)
    _seed_schedule_row(
        host,
        item_id="si-ml2-due",
        target_id="res-discourse-anyway",
        review_state="DUE",
        spacing_stage="STAGE_2",
        window_start=(now - timedelta(hours=1)).isoformat(),
        window_end=(now + timedelta(hours=1)).isoformat(),
    )
    _seed_schedule_row(
        host,
        item_id="si-ml2-overdue",
        target_id="res-hedge-i-think",
        review_state="OVERDUE",
        spacing_stage="STAGE_1",
        window_start=(now - timedelta(hours=3)).isoformat(),
        window_end=(now - timedelta(hours=1)).isoformat(),
    )
    _seed_schedule_row(
        host,
        item_id="si-ml2-upcoming",
        target_id="res-colloc-make-a-decision",
        review_state="UPCOMING",
        spacing_stage=None,
        window_start=(now + timedelta(hours=2)).isoformat(),
        window_end=(now + timedelta(hours=3)).isoformat(),
    )
    _seed_schedule_row(
        host,
        item_id="si-ml2-unwindowed",
        target_id="res-discourse-oh-well",
        review_state="NOT_SCHEDULED",
        spacing_stage=None,
        window_start=None,
        window_end=None,
    )
    host.db.commit()


def _seed_footprint(host: Any) -> None:
    """The footprint seeds: real turns, then claims over them — two ACTIVE
    claims on the second turn, one ACTIVE on the first, one SUPERSEDED and
    one INVALIDATED that must never count, and one ACTIVE claim for a
    different target that must never appear."""

    turn_ids = _seed_bare_turns(host, 3)
    created = "2026-10-03T08:00:00+00:00"
    _seed_evidence_group(host, "eg-ml2-0", turn_ids[0], created)
    _seed_evidence_group(host, "eg-ml2-1", turn_ids[1], created)
    _seed_claim(
        host,
        claim_id="ec-ml2-0",
        group_id="eg-ml2-0",
        target_id="res-discourse-anyway",
        turn_id=turn_ids[0],
        outcome="SUCCESS",
        status="ACTIVE",
        created_at=created,
    )
    _seed_claim(
        host,
        claim_id="ec-ml2-1",
        group_id="eg-ml2-1",
        target_id="res-discourse-anyway",
        turn_id=turn_ids[1],
        outcome="SUCCESS",
        status="ACTIVE",
        created_at=created,
    )
    _seed_claim(
        host,
        claim_id="ec-ml2-2",
        group_id="eg-ml2-1",
        target_id="res-discourse-anyway",
        turn_id=turn_ids[1],
        outcome="FAILURE",
        status="ACTIVE",
        created_at=created,
    )
    _seed_claim(
        host,
        claim_id="ec-ml2-3",
        group_id="eg-ml2-1",
        target_id="res-discourse-anyway",
        turn_id=turn_ids[1],
        outcome="SUCCESS",
        status="SUPERSEDED",
        created_at=created,
    )
    _seed_claim(
        host,
        claim_id="ec-ml2-4",
        group_id="eg-ml2-0",
        target_id="res-discourse-anyway",
        turn_id=turn_ids[0],
        outcome="SUCCESS",
        status="INVALIDATED",
        created_at=created,
    )
    _seed_claim(
        host,
        claim_id="ec-ml2-5",
        group_id="eg-ml2-1",
        target_id="res-hedge-i-think",
        turn_id=turn_ids[1],
        outcome="FAILURE",
        status="ACTIVE",
        created_at=created,
    )
    host.db.commit()


# ---------------------------------------------------------------------------
# 组① — the schedule zone's three honest states


def test_the_schedule_answers_honest_unavailable_without_the_leg(
    tmp_path: Path,
) -> None:
    """prep-1 档（无 content 腿 = 无 Scheduler）：available=false 的诚实
    空态——三桶全空、as_of 为 null，一个不虚构的排程都不给。"""

    with web_stack(tmp_path / "app.db") as stack:
        status, payload = stack.get_json("/api/schedule")
        assert status == 200
        assert payload == {
            "available": False,
            "as_of": None,
            "due": [],
            "overdue": [],
            "upcoming": [],
        }


def test_the_schedule_answers_honest_empty_with_the_leg_but_no_rows(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """有腿无行：available=true、as_of 在场、三桶全空——「没有排程」
    是读出来的事实，不是编的。"""

    with web_stack(
        tmp_path / "app.db", content_db=pilot_content_db
    ) as stack:
        status, payload = stack.get_json("/api/schedule")
        assert status == 200
        assert payload["available"] is True
        assert isinstance(payload["as_of"], str) and payload["as_of"]
        assert payload["due"] == []
        assert payload["overdue"] == []
        assert payload["upcoming"] == []


def test_the_schedule_serves_the_scheduler_own_buckets(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """有行：分档视图——DUE/OVERDUE/UPCOMING 各归其桶，行字段原值直出
    （窗口对、间隔阶原样、urgency 原值），无窗口的 NOT_SCHEDULED 行不进
    任何桶（视图自己的成员规则，如实转达）。"""

    with web_stack(
        tmp_path / "app.db",
        content_db=pilot_content_db,
        seed=_seed_windowed_schedule,
    ) as stack:
        status, payload = stack.get_json("/api/schedule")
        assert status == 200
        assert payload["available"] is True
        due_ids = [item["target_id"] for item in payload["due"]]
        overdue_ids = [item["target_id"] for item in payload["overdue"]]
        upcoming_ids = [item["target_id"] for item in payload["upcoming"]]
        assert due_ids == ["res-discourse-anyway"]
        assert overdue_ids == ["res-hedge-i-think"]
        assert upcoming_ids == ["res-colloc-make-a-decision"]
        everything = payload["due"] + payload["overdue"] + payload["upcoming"]
        assert "res-discourse-oh-well" not in [i["target_id"] for i in everything]
        due_row = payload["due"][0]
        assert due_row["name"] == "anyway"
        assert due_row["target_type"] == "RESOURCE"
        assert due_row["review_state"] == "DUE"
        assert due_row["spacing_stage"] == "STAGE_2"
        assert due_row["next_review_window_start"] is not None
        assert due_row["next_review_window_end"] is not None


# ---------------------------------------------------------------------------
# 组② — the history breadth parameters (default semantics unchanged)


def test_the_history_default_window_is_unchanged_and_honest(
    tmp_path: Path,
) -> None:
    """窗口默认语义钉：51 轮的通信，不带参数仍恰好 50 轮、最老在前、
    has_more=true；空通信 turns==[] 且 has_more=false（加性键不破旧面）。"""

    with web_stack(
        tmp_path / "app.db",
        seed=lambda host: _seed_bare_turns(host, DEFAULT_WINDOW + 1),
    ) as stack:
        status, payload = stack.get_json("/api/history")
        assert status == 200
        assert payload["window"] == DEFAULT_WINDOW
        assert payload["has_more"] is True
        turns = payload["turns"]
        assert len(turns) == DEFAULT_WINDOW
        # the most recent 50 of 51: the oldest seeded turn is the one the
        # window slides past
        assert turns[0]["user"] == "ml2 seed line 1"
        assert turns[-1]["user"] == f"ml2 seed line {DEFAULT_WINDOW}"
        status, payload = stack.get_json("/api/history?limit=50")
        assert status == 200
        assert payload["turns"] == turns


def test_the_history_limit_serves_the_most_recent_n(
    tmp_path: Path,
) -> None:
    """显式宽度：?limit=3 恰 3 轮（最近 3 封）、window=3、has_more 如实。"""

    with web_stack(
        tmp_path / "app.db", seed=lambda host: _seed_bare_turns(host, 5)
    ) as stack:
        status, payload = stack.get_json("/api/history?limit=3")
        assert status == 200
        assert payload["window"] == 3
        assert payload["has_more"] is True
        assert [t["user"] for t in payload["turns"]] == [
            "ml2 seed line 2",
            "ml2 seed line 3",
            "ml2 seed line 4",
        ]
        status, payload = stack.get_json("/api/history?limit=50")
        assert status == 200
        assert payload["window"] == 50
        assert payload["has_more"] is False
        assert len(payload["turns"]) == 5


def test_the_history_full_serves_the_whole_user_visible_transcript(
    tmp_path: Path,
) -> None:
    """?full=1：同一用户可见过滤面在全宽——51 轮全数在场、window=null、
    has_more 恒 false；窗口默认读面一字不变（默认 50 vs 全文 51）。"""

    with web_stack(
        tmp_path / "app.db",
        seed=lambda host: _seed_bare_turns(host, DEFAULT_WINDOW + 1),
    ) as stack:
        status, payload = stack.get_json("/api/history?full=1")
        assert status == 200
        assert payload["window"] is None
        assert payload["has_more"] is False
        turns = payload["turns"]
        assert len(turns) == DEFAULT_WINDOW + 1
        assert turns[0]["user"] == "ml2 seed line 0"
        assert turns[-1]["user"] == f"ml2 seed line {DEFAULT_WINDOW}"
        assert all(turn["assistant"] is None for turn in turns)


def test_the_history_breadth_grammar_is_fail_closed(tmp_path: Path) -> None:
    """文法：两参数互斥、full 只认 1、limit 只认从 1 起的整数、未知键
    自我点名——全是 400 人话，绝不静默。"""

    with web_stack(tmp_path / "app.db") as stack:
        for query, fragment in (
            ("?full=1&limit=3", "either"),
            ("?full=true", "1"),
            ("?limit=0", "from 1 up"),
            ("?limit=-2", "from 1 up"),
            ("?limit=lots", "whole number"),
            ("?bogus=1", "bogus"),
        ):
            status, payload = _get_status_json(stack, "/api/history" + query)
            assert status == 400, query
            assert fragment in payload["error"], query
        status, payload = stack.get_json("/api/history")
        assert status == 200
        assert payload["turns"] == []
        assert payload["has_more"] is False


# ---------------------------------------------------------------------------
# 组③ — the cross-letter footprint


def test_the_footprint_aggregates_active_evidence_over_turns(
    tmp_path: Path,
) -> None:
    """聚合钉：只数 ACTIVE（SUPERSEDED/INVALIDATED 不是足迹——§18）、
    按轮分布（轮次序数升序）、逐轮判分原值、他目标的证据不串门。"""

    with web_stack(
        tmp_path / "app.db", seed=_seed_footprint
    ) as stack:
        status, payload = stack.get_json(
            "/api/target_footprint?id=res-discourse-anyway"
        )
        assert status == 200
        assert payload["target_id"] == "res-discourse-anyway"
        assert payload["found"] is True
        assert payload["active_claim_count"] == 3
        turns = payload["turns"]
        assert len(turns) == 2
        first, second = turns
        assert first["turn_sequence"] == 1
        assert first["claim_count"] == 1
        assert first["outcomes"] == ["SUCCESS"]
        assert first["conversation_id"] == str(CONV)
        assert second["turn_sequence"] == 2
        assert second["claim_count"] == 2
        assert second["outcomes"] == ["SUCCESS", "FAILURE"]
        for turn in turns:
            assert turn["turn_id"]


def test_the_footprint_answers_honest_empty_for_unknown_targets(
    tmp_path: Path,
) -> None:
    """无证据的表达如实空：found=false 的 200 事实（词卡查无的姿态），
    绝不 404、绝不编一条足迹。缺 ?id 是 400 人话。"""

    with web_stack(
        tmp_path / "app.db", seed=_seed_footprint
    ) as stack:
        status, payload = stack.get_json(
            "/api/target_footprint?id=res-discourse-oh-well"
        )
        assert status == 200
        assert payload["target_id"] == "res-discourse-oh-well"
        assert payload["found"] is False
        assert payload["active_claim_count"] == 0
        assert payload["turns"] == []
        status, payload = _get_status_json(stack, "/api/target_footprint")
        assert status == 400
        assert "id" in payload["error"]


# ---------------------------------------------------------------------------
# 组④ — the sweep: zero residue of the retired wording, seams closed


def test_the_page_carries_the_three_faces_without_residue(
    tmp_path: Path,
) -> None:
    """页源扫全：新路由/新交互/新入口在场；退役句零残留（旧信档口径句、
    「跨信重现不做」）；检索自己的口径句照旧（它的读面没变）。"""

    web = Path(test_w1_web.__file__).parents[2] / "src" / "elc" / "web.py"
    source = web.read_text(encoding="utf-8")
    assert '"/api/schedule"' in source
    assert '"/api/target_footprint"' in source
    assert 'self.path.startswith("/api/history?")' in source
    assert "_history_request" in source
    with web_stack(tmp_path / "app.db") as stack:
        page = _page_source(stack)
    # the letters archive's load-earlier interaction and its new caliber
    assert "加载更早" in page
    assert "只摊开已加载的窗口——第 n 封按窗口里的顺序数" in page
    # the retired wordings are gone from the whole served source
    assert "只摊开已加载的最近 50 轮" not in page
    assert "跨信重现不做" not in page
    # the search section keeps its own (still true) caliber
    assert "只搜已加载的最近 50 轮。" in page
    # the schedule zone and the footprint entry ride their faces
    assert "loadScheduleZone" in page
    assert "复习调度腿没有装配" in page
    assert "footprintZone" in page
    assert "这个表达还没有留下学习足迹。" in page


def test_the_spec_seams_are_closed(tmp_path: Path) -> None:
    """spec 缝闭合：8.2.11 的「真全历史 = 数据缝」预告句退役；9.12-23④
    的主线-2 后记在场（历史登记原文保留——prep-0 R1 纪律，退役句扫全
    只对现役半区，「跨信重现不做」的历史登记原文不在其列）。"""

    spec = (
        Path(test_w1_web.__file__).parents[2]
        / "docs"
        / "FRONTEND_SPEC.md"
    ).read_text(encoding="utf-8")
    living = spec.split("> **时点限定**", 1)[0]
    assert "真「全历史」读面 = 数据缝" not in living
    assert "主线-2 后记" in spec
    assert "此缝由表达足迹读面闭合" in spec
    assert "跨信重现**不做**" not in living
