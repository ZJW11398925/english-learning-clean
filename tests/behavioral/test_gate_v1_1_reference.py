"""Behavioral baseline wiring — Teaching Gate v1.1 reference suite (BF-03).

Replays behavioral_baselines/gate/teaching_gate_reference_v1_1.py AS-IS
(loaded from its pinned file, never modified) against the 60-case v1.0
benchmark, upgrading each request per the v1.1 cross-layer repair
(behavioral_baselines/gate/BF-03_Gate_v1.1_CrossLayer_Revision.md;
docs/STATE_MACHINES.md §12.1 lines 380-383):

- authorization_basis: OPEN → DECISION_CYCLE, continuation → ACTIVE_MOMENT;
- authorization_status: VALID → VALID, STALE/INVALIDATED → INVALIDATED
  (a stale/invalidated opening decision is DENY AUTHORIZATION_INVALID,
  but staleness alone never invalidates continuation);
- USER_REQUESTED_CONTINUE defaults continuation_requested=True.

The gate of this suite is byte-level: every replayed result must equal the
committed artifact BF-03_v1_1_regression_results.json entry for the same
case id (error cases recorded there as result=null), and the artifact
itself must stay 60/60 pass. Degraded cases assert decision=None — no
synthetic DENY (docs/DATA_MODEL.md §14.1).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from typing import Any

from tests.conftest import BASELINES

GATE_DIR = BASELINES / "gate"
EXPECTED_BENCHMARK_CASES = 60

_STATUS_UPGRADE = {
    "VALID": "VALID",
    "STALE": "INVALIDATED",
    "INVALIDATED": "INVALIDATED",
}


def _load_reference() -> Any:
    path = GATE_DIR / "teaching_gate_reference_v1_1.py"
    spec = importlib.util.spec_from_file_location("gate_reference_v1_1", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.dont_write_bytecode = True  # keep the baseline tree byte-identical
    spec.loader.exec_module(module)
    return module


def _benchmark_cases() -> list[dict]:
    return json.loads(
        (GATE_DIR / "teaching_gate_benchmark_v1.json").read_text(encoding="utf-8")
    )


def _committed_results() -> dict[str, dict]:
    entries = json.loads(
        (GATE_DIR / "BF-03_v1_1_regression_results.json").read_text(encoding="utf-8")
    )
    return {entry["id"]: entry for entry in entries}


def _upgrade_request(request: dict) -> dict:
    """v1.0 benchmark request → v1.1 field set (BF-03 cross-layer repair)."""
    upgraded = dict(request)
    upgraded["authorization_basis"] = (
        "DECISION_CYCLE"
        if upgraded["gate_context"] == "OPEN"
        else "ACTIVE_MOMENT"
    )
    stale_field = upgraded.pop("decision_cycle_status", None)
    upgraded.setdefault(
        "authorization_status", _STATUS_UPGRADE.get(stale_field, "VALID")
    )
    if upgraded["gate_context"] == "USER_REQUESTED_CONTINUE":
        upgraded.setdefault("continuation_requested", True)
    return upgraded


def test_gate_benchmark_case_count_is_baseline() -> None:
    assert len(_benchmark_cases()) == EXPECTED_BENCHMARK_CASES


def test_gate_v1_1_replay_reproduces_committed_results() -> None:
    gate = _load_reference()
    committed = _committed_results()
    assert len(committed) == EXPECTED_BENCHMARK_CASES

    mismatches: list[str] = []
    for case in _benchmark_cases():
        expected_error = bool(case["expected"].get("error"))
        try:
            result: Any = gate.decide(_upgrade_request(case["request"]))
        except gate.GateInputError:
            result = None  # committed artifact records error cases as null
        if result != committed[case["id"]]["result"]:
            mismatches.append(
                f"{case['id']}: got {result!r}, committed "
                f"{committed[case['id']]['result']!r} (expected_error={expected_error})"
            )
    assert not mismatches, mismatches


def test_gate_degraded_cases_never_carry_a_synthetic_deny() -> None:
    """docs/DATA_MODEL.md §14.1: critical state UNKNOWN → GateExecutionStatus
    DEGRADED with GateDecision = none (never a synthetic DENY)."""
    gate = _load_reference()
    degraded = 0
    for case in _benchmark_cases():
        if not case["expected"].get("degraded"):
            continue
        degraded += 1
        result = gate.decide(_upgrade_request(case["request"]))
        assert result["decision"] is None, case["id"]
        assert result["execution_status"] == "DEGRADED", case["id"]
    assert degraded == 3  # benchmark ships exactly three degraded cases


def test_gate_committed_regression_artifacts_stay_all_pass() -> None:
    committed = _committed_results()
    assert all(entry.get("pass") for entry in committed.values())
    metamorphic = json.loads(
        (GATE_DIR / "metamorphic_results_v1.json").read_text(encoding="utf-8")
    )
    assert len(metamorphic) == 14
    assert all(entry.get("pass") for entry in metamorphic)
