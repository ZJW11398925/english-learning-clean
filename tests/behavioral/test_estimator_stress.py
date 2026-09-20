"""Behavioral baseline wiring — estimator stress suite (BF-01, 43 cases).

docs/IMPLEMENTATION_PLAN.md §13 requires the behavioral baseline assets to
ship with the repository and stay auto-regressable. The reference runner
(behavioral_baselines/estimator/run_stress.py) is executed as-is via
subprocess with the correct working directory — no wrapper logic re-derives
any expectation; this test only replays it and pins the case count.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

from tests.conftest import BASELINES

ESTIMATOR_DIR = BASELINES / "estimator"
RUNNER = "run_stress.py"
EXPECTED_CASES = 43


def test_estimator_stress_case_count_is_baseline() -> None:
    cases = json.loads(
        (ESTIMATOR_DIR / "estimator_stress_cases_v1_1.json").read_text()
    )
    assert len(cases) == EXPECTED_CASES


def test_estimator_stress_reference_passes_43_of_43() -> None:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    proc = subprocess.run(
        [sys.executable, RUNNER],
        cwd=ESTIMATOR_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert proc.returncode == 0, (
        f"estimator stress failed ({proc.returncode}):\n"
        f"{proc.stdout}\n{proc.stderr}"
    )
    assert f"Stress: {EXPECTED_CASES}/{EXPECTED_CASES} PASS" in proc.stdout
