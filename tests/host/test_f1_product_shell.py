"""F-1 — the product shell (产品壳): the dogfood page becomes a product face.

The server, the host and the online seed are the W-1 suite's own fixtures
(one serving stack, one production assembly); this file pins only the F-1
face on top:

1. the design language (F-1R) — the page's ``<style>`` is the VS1 letter
   token sheet (the archived chat parlor's ``chat.css``, value for value:
   the paper ground, the three ink levels, the two hairline rules, the
   ochre pencil, the touch wash, the three font stacks); the form laws
   are pinned as absolute negatives elsewhere (tests/host/
   test_f1r_letter_design.py: no tab bar, no teal, no radius, no shadow,
   no dark switch) and the sheet links no external resource at all
   (no CDN, no web font — ``dependencies = []`` stays true);
2. the screen navigation (F-1R) — three screens (开张 the first-visit
   cover / 客厅 the parlor / 仪表 the honest set screen), switched by
   plain JS show/hide (no router, no tab bar), the parlor header's
   仪表 link leading to the set screen, which holds the five why-panels
   and the observations readout;
3. the diagnostics face — ``GET /api/diagnostics`` answers the five whys
   read-only: over a real teaching chain the why-teach panel names the
   selected candidate and its ALLOW gate row; a fresh conversation answers
   the honest empty shapes; a seeded in-memory database pins the panel
   readings precisely (the not-activated candidates in ranking order with
   their utility against the activation threshold and the overexposure
   cost reading among the costs, the DENY reason codes, the evidence and
   support rows, the exposure count, the degraded ledgers, and the legacy
   factor_trace row stepped over); a database without the tables answers
   ``{"error": …}`` per panel, never a 500;
4. the face is silent — the read writes nothing: every diagnostics GET
   leaves the key tables' full content exactly where it was (content
   snapshot, so UPDATE-class mutations fail the pin too).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from elc.teaching.rollout import RolloutStage
from elc.web import _WebFace
from tests.host import test_w1_web
from tests.host.test_w1_web import (
    CONV,
    ERROR_TEXT,
    _page_source,
    seed_online,
    web_stack,
)

#: The W-1 suite's module-scoped pilot ``content.db`` fixture, bound under
#: the same name so pytest resolves it for this module's tests too.
pilot_content_db = test_w1_web.pilot_content_db

#: The letter token sheet, value for value — the one visual anchor is the
#: archived VS1 ``chat.css`` (values adopted, never its code): the page's
#: ``:root`` block and this table must agree.
LETTER_TOKENS: dict[str, str] = {
    "--bg": "#fbf9f4",
    "--ink": "#1b1a17",
    "--ink-soft": "#5c574e",
    "--ink-faint": "#726a5e",
    "--rule": "#ded7c9",
    "--rule-soft": "#ebe5d8",
    "--pencil": "#a8562f",
    "--touch": "#f0e9dc",
}

#: The three font stacks (serif for titles and letters, sans for the small
#: interface words, mono for the meters and the numbers), word for word.
LETTER_F_STACKS: tuple[str, ...] = (
    "--f-serif: Georgia, 'Times New Roman', 'Songti SC', 'SimSun',"
    " 'Noto Serif CJK SC', serif",
    "--f-sans: system-ui, -apple-system, 'Segoe UI', 'PingFang SC',"
    " 'Microsoft YaHei', sans-serif",
    "--f-mono: ui-monospace, 'Cascadia Mono', Consolas, monospace",
)

#: The layout pair: the reading gutter and the safe-area bottom inset.
LETTER_LAYOUT_TOKENS: dict[str, str] = {
    "--read-pad": "18px",
    "--safe-bottom": "env(safe-area-inset-bottom, 0px)",
}

_DIAG_PANEL_IDS = (
    "why-teach",
    "why-not-teach",
    "why-evidence",
    "why-support",
    "why-degraded",
)


def _page_of(tmp_path: Path) -> str:
    """The served page source, over the plain offline stack — the F-G1
    union: the shell plus every static asset it links."""

    with web_stack(tmp_path / "app.db") as stack:
        return _page_source(stack)


# ---------------------------------------------------------------------------
# 1. the design language — the two-theme token sheet


def test_the_page_carries_the_letter_tokens(tmp_path: Path) -> None:
    """The F-1R re-pin: the token sheet is chat.css's, value for value —
    the F-1 two-theme teal sheet is gone (one paper theme, no dark
    switch), and the three font stacks are spelled in full. The stacks
    are matched whitespace-normalized: CSS wraps a long stack across
    lines (ruff's own line length), and CSS itself is whitespace-blind —
    the family names and their order are what the pin holds."""

    page = " ".join(_page_of(tmp_path).split())
    for name, value in LETTER_TOKENS.items():
        assert f"{name}: {value}" in page, (name, value)
    for name, value in LETTER_LAYOUT_TOKENS.items():
        assert f"{name}: {value}" in page, (name, value)
    for stack in LETTER_F_STACKS:
        assert " ".join(stack.split()) in page, stack
    # one paper theme: the dark media-query sheet does not come back
    assert "@media (prefers-color-scheme: dark)" not in page


def test_the_page_links_no_external_resource(tmp_path: Path) -> None:
    """Zero external resources: no off-site URL of any scheme appears in
    the page source (the W-1 law, restated at product-shell scale)."""

    page = _page_of(tmp_path)
    assert "http://" not in page
    assert "https://" not in page
    assert "@import" not in page


# ---------------------------------------------------------------------------
# 2. the view navigation (F-2 migration: the two-tab pin became three-tab,
#    the assertions kept and re-truthed — 学习 between 聊天 and 诊断)


def test_the_page_has_the_three_screens(tmp_path: Path) -> None:
    """The R-1 re-pin of the navigation: 门厅 + 三空间 — the first-visit
    cover, the parlor, the study and the drawer — plain JS show/hide, no
    router, no tab bar; the dock (#18) is the only way between spaces
    (the old toggles and ways back retired — absence pins), and the
    study holds the five why-panels and the observations readout."""

    page = _page_of(tmp_path)
    # the vestibule and the three spaces (the form laws' negatives — no
    # tab bar, no teal — live in tests/host/test_f1r_letter_design.py)
    assert 'id="screen-onboard"' in page
    assert 'id="space-parlor"' in page
    assert 'id="space-study"' in page
    assert 'id="space-drawer"' in page
    # the old screens and their toggles/ways back are gone
    assert 'id="screen-living"' not in page
    assert 'id="screen-set"' not in page
    assert 'id="meter-toggle"' not in page
    assert ">仪表</button>" not in page
    assert 'id="back-to-living"' not in page
    assert "← 回客厅</button>" not in page
    # the switch is plain JS show/hide (no router library); the dock
    # carries the space switch
    assert "function showSpace(" in page
    assert "spaces[key].hidden = key !== name;" in page
    assert 'id="navdock"' in page
    # the study holds the five why-panels（R-1R：刷新钮全退——进节即拉是
    # 唯一拉取点，diag-refresh 缺位钉）
    for panel in _DIAG_PANEL_IDS:
        assert f'id="{panel}"' in page
    assert 'id="diag-refresh"' not in page
    # the diagnostics pull rides the read-only endpoint
    assert '"/api/diagnostics"' in page
    assert "loadDiagnostics" in page


# ---------------------------------------------------------------------------
# 3. the diagnostics face — the five whys


def test_diagnostics_over_a_real_teaching_chain(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """One error-text turn over the online chain, then the readout: the
    why-teach panel names the selected candidate and its ALLOW gate, the
    support panel names the teaching delivery, and the two honest empty
    panels stay empty (no attempt judged, nothing degraded)."""

    with web_stack(
        tmp_path / "app.db",
        content_db=pilot_content_db,
        stage=RolloutStage.STUDY_FIRST,
        seed=seed_online,
    ) as stack:
        status, data = stack.post("/api/turn", {"text": ERROR_TEXT})
        assert status == 200
        assert data["teaching_moments"][0]["focus_target_id"] == (
            test_w1_web.EV_TARGET
        )

        status, diag = stack.get_json("/api/diagnostics")
        assert status == 200
        assert set(diag) == {
            "why_teach",
            "why_not_teach",
            "evidence",
            "support",
            "degraded",
        }
        for panel in diag.values():
            assert "error" not in panel

        why_teach = diag["why_teach"]
        candidate = why_teach["candidate"]
        assert candidate is not None
        assert candidate["canonical_key"]
        assert candidate["selected"] is True
        assert candidate["activated"] is True
        assert candidate["utility"] is not None
        assert why_teach["created_at"] is not None
        assert why_teach["gate"]["decision"] == "ALLOW"
        assert isinstance(why_teach["gate"]["reason_codes"], list)

        why_not = diag["why_not_teach"]
        assert why_not["created_at"] is not None
        assert isinstance(why_not["candidates"], list)
        for silenced in why_not["candidates"]:
            assert silenced["activated"] is not True
            assert "utility" in silenced
            assert "activation_threshold" in silenced
            assert isinstance(silenced["costs"], list)
        assert why_not["gate_deny"] is None

        assert diag["evidence"]["records"] == []

        support = diag["support"]
        assert any(
            action["action_type"] == "TEACHING_OPEN"
            for action in support["actions"]
        )
        assert support["exposure_estimate_count"] >= 0

        assert diag["degraded"] == {
            "planner_execution": None,
            "runtime_outcome": None,
        }


def test_diagnostics_on_a_fresh_conversation_is_honestly_empty(
    tmp_path: Path,
) -> None:
    """No chain, no numbers: every panel answers its empty shape — the
    page will say 暂无数据 / 无降级记录, never a fabricated row."""

    with web_stack(tmp_path / "app.db") as stack:
        status, diag = stack.get_json("/api/diagnostics")
        assert status == 200
        assert diag["why_teach"] == {
            "created_at": None,
            "candidate": None,
            "gate": None,
        }
        assert diag["why_not_teach"]["created_at"] is None
        assert diag["why_not_teach"]["candidates"] == []
        assert diag["why_not_teach"]["gate_deny"] is None
        assert diag["evidence"]["records"] == []
        assert diag["support"]["actions"] == []
        assert diag["support"]["exposure_estimate_count"] == 0
        assert diag["degraded"] == {
            "planner_execution": None,
            "runtime_outcome": None,
        }
        for panel in diag.values():
            assert "error" not in panel


# -- the panel readings, pinned precisely on a seeded in-memory database ----
#
# The rows below are the migrations' own column names (the columns the
# panels SELECT, word for word from 0015 / 0007 / 0008 / 0003 / 0018; the
# columns no panel reads are omitted). The factor_trace documents are
# spelled in the trace document's own payload shape (elc.planner.
# trace_document's ``ft1`` encoding) so the decoder takes them unmodified.

_DIAG_SCHEMA = """
CREATE TABLE planner_evaluation (
    planner_evaluation_id TEXT PRIMARY KEY,
    decision_cycle_id TEXT,
    frontier_candidate_ids TEXT,
    ranked_candidate_ids TEXT,
    factor_trace TEXT,
    planner_version TEXT,
    policy_profile_version TEXT,
    created_at TEXT
);
CREATE TABLE gate_decision (
    gate_decision_id TEXT PRIMARY KEY,
    decision_cycle_id TEXT,
    candidate_id TEXT,
    context TEXT,
    decision TEXT,
    reason_codes TEXT,
    policy_version TEXT,
    created_at TEXT
);
CREATE TABLE attempt_evaluation_record (
    attempt_evaluation_id TEXT PRIMARY KEY,
    moment_id TEXT,
    attempt_id TEXT,
    evaluator_id TEXT,
    evaluator_version TEXT,
    outcome TEXT,
    confidence REAL,
    evidence_proposal_refs TEXT,
    created_at TEXT
);
CREATE TABLE generation_action_intent (
    action_id TEXT PRIMARY KEY,
    turn_id TEXT,
    decision_cycle_id TEXT,
    moment_id TEXT,
    assistant_turn_id TEXT,
    action_type TEXT,
    generation_contract_id TEXT,
    status TEXT,
    attempt_count INTEGER,
    owner_epoch INTEGER,
    created_at TEXT
);
CREATE TABLE exposure_estimate (
    action_id TEXT PRIMARY KEY,
    certainty TEXT,
    exposure_level TEXT,
    max_possible_exposure TEXT,
    confirmed_exposure TEXT,
    derivation_reason TEXT
);
CREATE TABLE planner_execution_status (
    decision_cycle_id TEXT PRIMARY KEY,
    status TEXT,
    error_code TEXT,
    created_at TEXT
);
CREATE TABLE runtime_decision_outcome (
    turn_id TEXT PRIMARY KEY,
    decision_cycle_id TEXT,
    outcome TEXT,
    reason_codes TEXT,
    created_at TEXT
);
"""


class _DiagHost:
    """Just enough host for the diagnostics face: one plain sqlite
    connection, nothing else (the ``_WebFace`` unit seam)."""

    app_db_path = "stub-app.db"

    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db

    @property
    def db(self) -> sqlite3.Connection:
        return self._db


def _candidate_trace(
    candidate_id: str,
    canonical_key: str,
    *,
    utility: float | None,
    threshold: float | None,
    activated: bool | None,
    selected: bool,
    costs: tuple[tuple[str, float], ...] = (),
) -> dict[str, Any]:
    """One candidate trace, in the ``ft1`` document's own payload shape."""

    return {
        "candidate_id": candidate_id,
        "canonical_key": canonical_key,
        "merged_from": [],
        "initiative_class": "AUTOMATIC",
        "request_priority": 0,
        "coverage_service_state": "NONE",
        "benefit": [],
        "cost": [
            {"factor": factor, "value": value, "source": "DECLARED",
             "authority": None}
            for factor, value in costs
        ],
        "gaps": [],
        "excluded": None,
        "benefit_score": 0.8,
        "cost_score": 0.3,
        "coverage_service_bonus": 0.0,
        "utility": utility,
        "activation_path": None,
        "activation_threshold": threshold,
        "activated": activated,
        "dominated_by": [],
        "in_tie_set": False,
        "selected": selected,
    }


def _factor_trace_document(candidates: list[dict[str, Any]]) -> str:
    """The candidates as the column's bytes (the ``ft1`` encoding)."""

    return json.dumps(
        {
            "version": "ft1",
            "provenance": "KERNEL_TRACE",
            "reasons": ["the run's own prose"],
            "candidates": candidates,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _seeded_diag_db() -> sqlite3.Connection:
    """One evaluation that selected ``c-a`` plus two silenced candidates, a
    DENY elsewhere, judged attempts, teaching deliveries with exposure
    estimates, and one degraded row on each ledger."""

    conn = sqlite3.connect(":memory:")
    conn.executescript(_DIAG_SCHEMA)
    trace = _factor_trace_document(
        [
            _candidate_trace(
                "c-a", "anyway",
                utility=0.62, threshold=0.195, activated=True, selected=True,
                costs=(("interruption_cost", 0.2),),
            ),
            _candidate_trace(
                "c-b", "got-it",
                utility=0.1735, threshold=0.195, activated=False,
                selected=False,
                costs=(("overexposure", 0.4), ("user_resistance", 0.3)),
            ),
            _candidate_trace(
                "c-c", "to-be-honest",
                utility=None, threshold=None, activated=None, selected=False,
            ),
        ]
    )
    conn.execute(
        "INSERT INTO planner_evaluation VALUES (?,?,?,?,?,?,?,?)",
        (
            "ev-1", "cycle-1", '["c-a","c-b","c-c"]',
            '["c-a","c-b","c-c"]', trace, "pv", "policy",
            "2026-09-28T10:00:00+00:00",
        ),
    )
    conn.execute(
        "INSERT INTO gate_decision VALUES (?,?,?,?,?,?,?,?)",
        (
            "g-1", "cycle-1", "c-a", "OPEN", "ALLOW", '["OPPORTUNITY"]',
            "pv", "2026-09-28T10:00:01+00:00",
        ),
    )
    conn.execute(
        "INSERT INTO gate_decision VALUES (?,?,?,?,?,?,?,?)",
        (
            "g-2", "cycle-2", "c-z", "OPEN", "DENY",
            '["HARD_COOLDOWN_ACTIVE"]', "pv",
            "2026-09-28T10:01:00+00:00",
        ),
    )
    conn.execute(
        "INSERT INTO attempt_evaluation_record VALUES (?,?,?,?,?,?,?,?,?)",
        (
            "ae-1", "m-1", "at-1", "eval", "v1", "FAILURE", 0.9, "[]",
            "2026-09-28T10:02:00+00:00",
        ),
    )
    conn.execute(
        "INSERT INTO attempt_evaluation_record VALUES (?,?,?,?,?,?,?,?,?)",
        (
            "ae-2", "m-1", "at-2", "eval", "v1", "SUCCESS", 0.95, "[]",
            "2026-09-28T10:03:00+00:00",
        ),
    )
    for row in (
        (
            "act-1", "t-1", None, None, "at-1", "TEACHING_OPEN", "gc",
            "TERMINAL", 0, 1, "2026-09-28T10:00:05+00:00",
        ),
        (
            "act-2", "t-1", None, None, "at-2", "TEACHING_HINT", "gc",
            "TERMINAL", 0, 1, "2026-09-28T10:00:06+00:00",
        ),
        (
            "act-3", "t-1", None, None, "at-3", "NORMAL_PERSONA_REPLY", "gc",
            "TERMINAL", 0, 1, "2026-09-28T10:00:07+00:00",
        ),
    ):
        conn.execute(
            "INSERT INTO generation_action_intent VALUES"
            " (?,?,?,?,?,?,?,?,?,?,?)",
            row,
        )
    conn.execute(
        "INSERT INTO exposure_estimate VALUES (?,?,?,?,?,?)",
        ("act-1", "CONFIRMED", "FULL", "FULL", "FULL", "delivered"),
    )
    conn.execute(
        "INSERT INTO exposure_estimate VALUES (?,?,?,?,?,?)",
        ("act-2", "CONFIRMED", "PARTIAL", "FULL", "PARTIAL", "delivered"),
    )
    conn.execute(
        "INSERT INTO planner_execution_status VALUES (?,?,?,?)",
        (
            "cycle-1", "SUCCEEDED", None,
            "2026-09-28T10:00:02+00:00",
        ),
    )
    conn.execute(
        "INSERT INTO planner_execution_status VALUES (?,?,?,?)",
        ("cycle-2", "DEGRADED", "ERR_X", "2026-09-28T10:01:01+00:00"),
    )
    conn.execute(
        "INSERT INTO runtime_decision_outcome VALUES (?,?,?,?,?)",
        ("t-1", "cycle-1", "NORMAL", "[]", "2026-09-28T10:00:03+00:00"),
    )
    conn.execute(
        "INSERT INTO runtime_decision_outcome VALUES (?,?,?,?,?)",
        (
            "t-2", "cycle-2", "DEGRADED_NO_AUTOMATIC_TEACHING",
            '["PROVENANCE_FACE_MISSING"]', "2026-09-28T10:01:03+00:00",
        ),
    )
    conn.commit()
    return conn


def test_the_diagnostic_panels_read_the_durable_rows_precisely() -> None:
    """The readings, value for value: the selected candidate with its ALLOW
    gate; the silenced candidates in ranking order (the overexposure band
    value among the costs, the utility against the threshold); the DENY
    reason codes; the newest-first lists and the exposure count; the
    degraded rows (the healthy rows on the same tables are not the answer);
    and a legacy prose factor_trace row is stepped over, not guessed."""

    face = _WebFace(_DiagHost(_seeded_diag_db()), str(CONV))  # type: ignore[arg-type]
    diag = face.diagnostics()

    why_teach = diag["why_teach"]
    assert why_teach["created_at"] == "2026-09-28T10:00:00+00:00"
    assert why_teach["candidate"] == {
        "candidate_id": "c-a",
        "canonical_key": "anyway",
        "benefit_score": 0.8,
        "cost_score": 0.3,
        "utility": 0.62,
        "activation_threshold": 0.195,
        "activated": True,
        "selected": True,
        "costs": [{"factor": "interruption_cost", "value": 0.2}],
    }
    assert why_teach["gate"] == {
        "decision": "ALLOW",
        "reason_codes": ["OPPORTUNITY"],
        "created_at": "2026-09-28T10:00:01+00:00",
    }

    why_not = diag["why_not_teach"]
    assert why_not["created_at"] == "2026-09-28T10:00:00+00:00"
    assert [c["candidate_id"] for c in why_not["candidates"]] == ["c-b", "c-c"]
    silenced = why_not["candidates"][0]
    assert silenced["activated"] is False
    assert silenced["utility"] == 0.1735
    assert silenced["activation_threshold"] == 0.195
    assert silenced["costs"] == [
        {"factor": "overexposure", "value": 0.4},
        {"factor": "user_resistance", "value": 0.3},
    ]
    assert why_not["gate_deny"] == {
        "reason_codes": ["HARD_COOLDOWN_ACTIVE"],
        "created_at": "2026-09-28T10:01:00+00:00",
    }

    assert diag["evidence"]["records"] == [
        {
            "outcome": "SUCCESS",
            "confidence": 0.95,
            "created_at": "2026-09-28T10:03:00+00:00",
        },
        {
            "outcome": "FAILURE",
            "confidence": 0.9,
            "created_at": "2026-09-28T10:02:00+00:00",
        },
    ]

    actions = diag["support"]["actions"]
    assert [action["action_type"] for action in actions] == [
        "TEACHING_HINT",
        "TEACHING_OPEN",
    ]
    assert diag["support"]["exposure_estimate_count"] == 2

    assert diag["degraded"]["planner_execution"] == {
        "status": "DEGRADED",
        "error_code": "ERR_X",
        "created_at": "2026-09-28T10:01:01+00:00",
    }
    assert diag["degraded"]["runtime_outcome"] == {
        "outcome": "DEGRADED_NO_AUTOMATIC_TEACHING",
        "reason_codes": ["PROVENANCE_FACE_MISSING"],
        "created_at": "2026-09-28T10:01:03+00:00",
    }


def test_a_legacy_factor_trace_row_is_stepped_over_not_guessed() -> None:
    """A P9-0 predecessor row (a bare prose array, no candidate trace) has
    no selected candidate to offer: the why-teach panel answers the honest
    empty shape, and the why-not panel answers the row's existence without
    inventing candidates."""

    conn = sqlite3.connect(":memory:")
    conn.executescript(_DIAG_SCHEMA)
    conn.execute(
        "INSERT INTO planner_evaluation VALUES (?,?,?,?,?,?,?,?)",
        (
            "ev-old", "cycle-old", "[]", "[]", '["the run went as it did"]',
            "pv", "policy", "2026-09-28T09:00:00+00:00",
        ),
    )
    conn.commit()
    face = _WebFace(_DiagHost(conn), str(CONV))  # type: ignore[arg-type]
    diag = face.diagnostics()
    assert diag["why_teach"] == {
        "created_at": None,
        "candidate": None,
        "gate": None,
    }
    assert diag["why_not_teach"]["created_at"] == (
        "2026-09-28T09:00:00+00:00"
    )
    assert diag["why_not_teach"]["candidates"] == []


def test_the_diagnostic_panels_survive_a_dirty_database() -> None:
    """A database without the tables answers ``{"error": …}`` in each
    panel's own slot — the other four panels would still answer, and the
    route never 500s the whole readout."""

    conn = sqlite3.connect(":memory:")
    face = _WebFace(_DiagHost(conn), str(CONV))  # type: ignore[arg-type]
    diag = face.diagnostics()
    assert set(diag) == {
        "why_teach",
        "why_not_teach",
        "evidence",
        "support",
        "degraded",
    }
    for panel in diag.values():
        assert set(panel) == {"error"}
        assert "OperationalError" in panel["error"]


# ---------------------------------------------------------------------------
# 4. the face is silent — read-only, pinned by a content snapshot


def test_the_diagnostics_face_is_read_only(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """Three diagnostics GETs over a chain that really taught: every key
    table's full content stays exactly where the turn left it — the
    readout reads, it never writes. The snapshot is content-level (every
    row, not just the max ``rowid``): an UPDATE-class mutation inside a
    panel would change a row and fail here just the same (review L-1)."""

    app_db = tmp_path / "app.db"
    tables = (
        "turn_record",
        "teaching_moment",
        "gate_decision",
        "planner_evaluation",
        "attempt_evaluation_record",
        "generation_action_intent",
        "exposure_estimate",
        "planner_execution_status",
        "runtime_decision_outcome",
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
            status, diag = stack.get_json("/api/diagnostics")
            assert status == 200
            assert "error" not in diag["why_teach"]
        assert snapshot() == before
