"""Behavioral baseline wiring — Local Runtime reference suite (BF-07, 43 checks).

Replays behavioral_baselines/runtime/run_local_runtime_tests.py AS-IS via a
subprocess (the file is byte-pinned baseline evidence and is not modified):

- Windows adaptation: the reference suite keeps sqlite connections open
  while its file-backed checks (L24–L30) run inside a TemporaryDirectory;
  Windows cannot unlink open files, so CLEANUP raises PermissionError(13)
  after the check verdict was already computed. The subprocess gets a
  best-effort-cleanup TemporaryDirectory via tests/_compat/sitecustomize.py
  injected through PYTHONPATH (win32 only; POSIX keeps pristine semantics).
- The runner rewrites its two result JSONs inside behavioral_baselines/ on
  every run; the baseline tree must stay byte-identical, so this test
  snapshots those files beforehand and restores them in a `finally`.
- No JSON artifact is trusted as the verdict: the subprocess exit code and
  the runner's printed tally decide pass/fail.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from tests.conftest import BASELINES, REPO_ROOT

RUNTIME_DIR = BASELINES / "runtime"
RUNNER = RUNTIME_DIR / "run_local_runtime_tests.py"
COMPAT_DIR = REPO_ROOT / "tests" / "_compat"
EXPECTED_CHECKS = 43
# Files the runner rewrites inside the baseline tree (must be restored).
RUNNER_WRITES = ("local_runtime_test_results_v1.json", "test_summary.json")


def _child_env() -> dict[str, str]:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = f"{COMPAT_DIR}{os.pathsep}{existing}" if existing else str(
        COMPAT_DIR
    )
    return env


def test_local_runtime_reference_passes_43_of_43() -> None:
    saved: dict[Path, bytes] = {}
    try:
        for name in RUNNER_WRITES:
            path = RUNTIME_DIR / name
            if path.exists():
                saved[path] = path.read_bytes()

        proc = subprocess.run(
            [sys.executable, str(RUNNER)],
            cwd=RUNTIME_DIR,
            env=_child_env(),
            capture_output=True,
            text=True,
            timeout=600,
        )
    finally:
        for path, payload in saved.items():
            path.write_bytes(payload)

    assert proc.returncode == 0, (
        f"local runtime reference suite failed ({proc.returncode}):\n"
        f"{proc.stdout}\n{proc.stderr}"
    )
    assert f"Local runtime checks: {EXPECTED_CHECKS}/{EXPECTED_CHECKS} PASS" in (
        proc.stdout
    )
