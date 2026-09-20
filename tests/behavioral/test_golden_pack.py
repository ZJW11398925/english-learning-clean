"""Behavioral baseline wiring — Golden cross-layer pack (BF-04/BF-05 assets).

Replays behavioral_baselines/golden/run_golden_pack.py AS-IS via subprocess
(the file is byte-pinned baseline evidence). The runner rewrites
golden_results_v1.json in the baseline tree on every run; the baseline tree
must stay byte-identical, so this test snapshots that file beforehand and
restores it in a `finally` — after the run `git status` must be clean.

The verdict comes from the subprocess exit code and the runner's printed
tally, never from the (rewritten) JSON artifact.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from tests.conftest import BASELINES

GOLDEN_DIR = BASELINES / "golden"
RUNNER = GOLDEN_DIR / "run_golden_pack.py"
EXPECTED_SCENARIOS = 28
# Files the runner rewrites inside the baseline tree (must be restored).
RUNNER_WRITES = ("golden_results_v1.json",)


def test_golden_pack_passes_28_of_28() -> None:
    saved: dict[Path, bytes] = {}
    try:
        for name in RUNNER_WRITES:
            path = GOLDEN_DIR / name
            if path.exists():
                saved[path] = path.read_bytes()

        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        proc = subprocess.run(
            [sys.executable, str(RUNNER)],
            cwd=GOLDEN_DIR,
            env=env,
            capture_output=True,
            text=True,
            timeout=600,
        )
    finally:
        for path, payload in saved.items():
            path.write_bytes(payload)

    assert proc.returncode == 0, (
        f"golden pack failed ({proc.returncode}):\n{proc.stdout}\n{proc.stderr}"
    )
    assert f"Golden scenarios: {EXPECTED_SCENARIOS}/{EXPECTED_SCENARIOS} PASS" in (
        proc.stdout
    )
    # The rewritten artifact must be byte-identical to the snapshot: the
    # committed golden_results_v1.json IS a full pass record.
    for name in RUNNER_WRITES:
        path = GOLDEN_DIR / name
        assert path in saved, f"{name} vanished from the baseline tree"
        assert path.read_bytes() == saved[path], (
            f"{name} changed on disk after restore"
        )


def test_golden_committed_results_are_all_pass() -> None:
    import json

    results = json.loads(
        (GOLDEN_DIR / "golden_results_v1.json").read_text(encoding="utf-8")
    )
    assert len(results) == EXPECTED_SCENARIOS
    assert all(entry.get("pass") for entry in results)
