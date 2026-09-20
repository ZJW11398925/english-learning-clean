"""Platform gate — docs/run_post_bf_regression.py cannot run from this layout.

This is the explicit skip marker required by the task book ("修复路径不通时
做显式平台门，绝不伪装通过"). The gate is NOT Windows-specific: the runner
is structurally broken in this repository on every platform.

Measured evidence (this repo, 2026-09-20):

1. WinError 267 (The directory name is invalid). The runner computes
   `ROOT = Path(__file__).resolve().parent` (line 3) — it lives in docs/, so
   ROOT=docs/. Line 4 then derives `B = ROOT/'behavioral_baselines'`
   (docs/behavioral_baselines — does not exist; the asset tree is at the
   repo root). Every `run_py(...)` call (lines 8-15) passes
   `cwd=path.parent` under that missing tree, so the very first subprocess
   raises WinError 267.

2. Even re-homing the script at the repo root would not fix it: line 117
   reads the six canonical docs as `(ROOT/n)` — from the repo root that
   resolves to PRODUCT_CONTRACT.md etc. outside docs/ and raises
   FileNotFoundError. The two sections require two different ROOTs inside
   one file, so no working-directory or __file__ shim can satisfy both.

3. Fixing the script in place is not ours to do: it is baseline evidence —
   its SHA-256 is pinned in docs/manifest.json ("run_post_bf_regression.py"
   hash) — and the task book red-lines edits to docs/ and
   behavioral_baselines/. Hence: explicit gate, not a silent skip and not a
   doctored pass.

Coverage note: the runner's four behavioral suites are individually wired in
this directory instead — estimator stress and planner stress via subprocess,
the local runtime reference via the Windows-tolerant driver, and the
gate/security/modality benchmark assets are pinned by their committed
result files (BF-03_v1_1_regression_results.json, metamorphic_results_v1.json,
POST_BF_REGRESSION_RESULTS.json 60/60).
"""

from __future__ import annotations

import pytest

from tests.conftest import REPO_ROOT

RUNNER = REPO_ROOT / "docs" / "run_post_bf_regression.py"

GATE_REASON = (
    "docs/run_post_bf_regression.py 结构性路径错误（平台无关）：ROOT=__file__ "
    ".parent 指向 docs/，behavioral_baselines 却在仓库根 → 首个 subprocess "
    "cwd 不存在，WinError 267；从仓库根运行则第 117 行读六文档改为 "
    "FileNotFoundError。同一文件内两处 ROOT 假设互相矛盾，无法用 cwd/加载 "
    "垫片修复；原件哈希被 docs/manifest.json 钉住，属基线证据不可改。四个 "
    "行为套件已在本目录逐一套件接线。"
)


def test_docs_runner_exists_unmodified() -> None:
    """The runner ships untouched (byte-pinned in docs/manifest.json)."""
    import hashlib
    import json

    assert RUNNER.exists()
    manifest = json.loads((REPO_ROOT / "docs" / "manifest.json").read_text())
    pinned = manifest["hashes"]["run_post_bf_regression.py"]
    actual = hashlib.sha256(RUNNER.read_bytes()).hexdigest()
    assert actual == pinned, "docs/run_post_bf_regression.py drifted from baseline"


@pytest.mark.skipif(True, reason=GATE_REASON)
def test_post_bf_regression_runner_is_gated_on_this_layout() -> None:
    """Would replay docs/run_post_bf_regression.py if the layout contradiction
    were ever fixed upstream; skipped until then (see module docstring)."""
    raise NotImplementedError("unreachable while the gate holds")
