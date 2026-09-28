"""F-1 — the product shell (产品壳): the dogfood page becomes a product face.

The server, the host and the online seed are the W-1 suite's own fixtures
(one serving stack, one production assembly); this file pins only the F-1
face on top:

1. the design language — the page's ``<style>`` is a two-theme token sheet
   (the light values on ``:root``, the dark values under
   ``@media (prefers-color-scheme: dark)``), every token value spelled in
   full and pinned here by name, with the shared radius / motion / tabbar
   tokens and the focus ring; the sheet links no external resource at all
   (no CDN, no web font — ``dependencies = []`` stays true);
2. the two-view navigation — a fixed bottom tab bar with exactly two tabs
   (聊天 default / 诊断), switched by plain JS show/hide (no router), the
   diagnostics view holding the five why-panels and the observations
   readout;
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
   leaves the key tables' ``rowid`` maxima exactly where they were.
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
    seed_online,
    web_stack,
)

#: The W-1 suite's module-scoped pilot ``content.db`` fixture, bound under
#: the same name so pytest resolves it for this module's tests too.
pilot_content_db = test_w1_web.pilot_content_db

#: The light-theme token sheet, value for value (the design language's one
#: origin — the page's ``:root`` block and this table must agree).
LIGHT_TOKENS: dict[str, str] = {
    "--bg": "#faf8f5",
    "--surface": "#ffffff",
    "--surface-sunken": "#f3f0eb",
    "--ink": "#1a1815",
    "--ink-soft": "#6d675e",
    "--ink-faint": "#98918a",
    "--line": "#e8e3db",
    "--line-strong": "#d8d1c7",
    "--accent": "#0f766e",
    "--accent-press": "#0b5d56",
    "--accent-wash": "#e9f3f1",
    "--on-accent": "#ffffff",
    "--danger": "#b3261e",
    "--danger-wash": "#fdeceb",
    "--ok": "#3f6212",
}

#: The dark-theme sheet, under ``@media (prefers-color-scheme: dark)`` —
#: warm black, not pure black; the same token names, the dark values.
DARK_TOKENS: dict[str, str] = {
    "--bg": "#161513",
    "--surface": "#201e1b",
    "--surface-sunken": "#1a1917",
    "--ink": "#f2efe9",
    "--ink-soft": "#a8a199",
    "--ink-faint": "#7d766e",
    "--line": "#2f2c28",
    "--line-strong": "#403c37",
    "--accent": "#4fd1c5",
    "--accent-press": "#38b2a8",
    "--accent-wash": "#12302d",
    "--on-accent": "#08201e",
    "--danger": "#ff8a80",
    "--danger-wash": "#331b19",
    "--ok": "#a3c96b",
}

#: The theme-independent tokens: radii, motion, the tab bar's height.
SHARED_TOKENS: dict[str, str] = {
    "--r-sm": "8px",
    "--r": "12px",
    "--r-lg": "16px",
    "--r-xl": "22px",
    "--dur": "180ms",
    "--tabbar-h": "64px",
}

_DIAG_PANEL_IDS = (
    "why-teach",
    "why-not-teach",
    "why-evidence",
    "why-support",
    "why-degraded",
)


def _page_of(tmp_path: Path) -> str:
    """The served page source, over the plain offline stack."""

    with web_stack(tmp_path / "app.db") as stack:
        status, _, body = stack.get_raw("/")
        assert status == 200
        return body.decode("utf-8")


# ---------------------------------------------------------------------------
# 1. the design language — the two-theme token sheet


def test_the_page_carries_both_theme_token_sheets(tmp_path: Path) -> None:
    page = _page_of(tmp_path)
    for sheet in (LIGHT_TOKENS, DARK_TOKENS):
        for name, value in sheet.items():
            assert f"{name}: {value}" in page, (name, value)
    for name, value in SHARED_TOKENS.items():
        assert f"{name}: {value}" in page, (name, value)
    # the dark sheet is a media-query switch, not a script or a toggle
    assert "@media (prefers-color-scheme: dark)" in page
    # the one motion curve and the focus ring, spelled in full
    assert "--ease: cubic-bezier(0.2, 0, 0.2, 1)" in page
    assert (
        "--ring: 0 0 0 3px"
        " color-mix(in srgb, var(--accent) 28%, transparent)" in page
    )


def test_the_page_links_no_external_resource(tmp_path: Path) -> None:
    """Zero external resources: no off-site URL of any scheme appears in
    the page source (the W-1 law, restated at product-shell scale)."""

    page = _page_of(tmp_path)
    assert "http://" not in page
    assert "https://" not in page
    assert "@import" not in page


# ---------------------------------------------------------------------------
# 2. the two-view navigation


def test_the_page_has_the_two_view_navigation(tmp_path: Path) -> None:
    page = _page_of(tmp_path)
    # the fixed bottom tab bar, two tabs, the words a person reads
    assert 'class="tabbar"' in page
    assert ">聊天</button>" in page
    assert ">诊断</button>" in page
    assert 'data-view="chat"' in page
    assert 'data-view="diagnostics"' in page
    # the two view containers, chat the default and diagnostics hidden
    assert 'id="view-chat"' in page
    assert 'id="view-diagnostics"' in page
    # the switch is plain JS show/hide (no router library)
    assert "function showView(" in page
    assert 'tab.setAttribute("aria-current", "page")' in page
    assert ".hidden = " in page
    # the diagnostics view holds the five why-panels and a refresh
    for panel in _DIAG_PANEL_IDS:
        assert f'id="{panel}"' in page
    assert 'id="diag-refresh"' in page
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
# 4. the face is silent — read-only, pinned by rowid maxima


def test_the_diagnostics_face_is_read_only(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """Three diagnostics GETs over a chain that really taught: every key
    table's last ``rowid`` stays exactly where the turn left it — the
    readout reads, it never writes."""

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

    def maxima() -> dict[str, int]:
        ro = sqlite3.connect(f"file:{app_db}?mode=ro", uri=True)
        try:
            return {
                table: int(
                    ro.execute(
                        f"SELECT COALESCE(MAX(rowid), 0) FROM {table}"
                    ).fetchone()[0]
                )
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
        before = maxima()
        for _ in range(3):
            status, diag = stack.get_json("/api/diagnostics")
            assert status == 200
            assert "error" not in diag["why_teach"]
        assert maxima() == before
