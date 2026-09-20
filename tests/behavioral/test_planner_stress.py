"""Behavioral baseline wiring — planner stress suite (BF-02, 43 cases).

Same contract as the estimator wiring: the reference runner
(behavioral_baselines/planner/run_stress.py) is replayed as-is via
subprocess; this test pins the case count and asserts a clean exit.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

from tests.conftest import BASELINES

PLANNER_DIR = BASELINES / "planner"
RUNNER = "run_stress.py"
EXPECTED_CASES = 43


def test_planner_stress_case_count_is_baseline() -> None:
    cases = json.loads(
        (PLANNER_DIR / "planner_stress_cases_v1_1.json").read_text()
    )
    assert len(cases) == EXPECTED_CASES


def test_planner_stress_reference_passes_43_of_43() -> None:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    proc = subprocess.run(
        [sys.executable, RUNNER],
        cwd=PLANNER_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert proc.returncode == 0, (
        f"planner stress failed ({proc.returncode}):\n{proc.stdout}\n{proc.stderr}"
    )
    assert f"Stress: {EXPECTED_CASES}/{EXPECTED_CASES} PASS" in proc.stdout
