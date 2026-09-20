"""docs/run_post_bf_regression.py — byte-pinned baseline evidence, gated
by real assertions instead of a skip.

The runner cannot execute from this repository layout: it computes
`ROOT = Path(__file__).resolve().parent` (docs/, line 3) and derives
`B = ROOT/'behavioral_baselines'` (line 4) — docs/behavioral_baselines,
which does not exist here — while its cross-document section (line 117)
reads the six canonical docs as `ROOT/<name>`, which only resolves when
ROOT is the repo root. The two ROOT assumptions contradict each other, so
no working directory or shim can satisfy both. The file is baseline
evidence (SHA-256 pinned in docs/manifest.json) and is not modified.

Instead of a permanent skip, this module asserts:
1. the pinned original is byte-identical to the manifest pin;
2. the layout contradiction is real right now (both halves, not folklore);
3. the runner's four behavioral suites are each wired as repo-native
   suites in this directory — the actual regression coverage the runner
   would have provided.
"""

from __future__ import annotations

import hashlib
import importlib
import json

from tests.conftest import DOCS_ROOT, REPO_ROOT

RUNNER = DOCS_ROOT / "run_post_bf_regression.py"
MANIFEST = DOCS_ROOT / "manifest.json"
# Manifest key for the pinned original (repo-true path; see R5 cleanup).
MANIFEST_RUNNER_KEY = "docs/run_post_bf_regression.py"

# The runner's four behavioral suites and the repo-native modules that
# replay them (estimator/planner/runtime were already wired; gate v1.1,
# golden, security, modality were added by external review R3).
SUITE_WIRING = {
    "Estimator stress": ("tests.behavioral.test_estimator_stress",
                         "test_estimator_stress_reference_passes_43_of_43"),
    "Planner stress": ("tests.behavioral.test_planner_stress",
                       "test_planner_stress_reference_passes_43_of_43"),
    "Golden cross-layer pack": ("tests.behavioral.test_golden_pack",
                                "test_golden_pack_passes_28_of_28"),
    "Local runtime integration": ("tests.behavioral.test_local_runtime_reference",
                                  "test_local_runtime_reference_passes_43_of_43"),
    # The runner's record-only sections (gate regression / security /
    # modality benchmarks) are replayed, not just pinned:
    "Gate v1.1 benchmark": ("tests.behavioral.test_gate_v1_1_reference",
                            "test_gate_v1_1_replay_reproduces_committed_results"),
    "Security benchmark": ("tests.behavioral.test_security_reference",
                           "test_security_reference_passes_61_of_61"),
    "Modality benchmark": ("tests.behavioral.test_modality_reference",
                           "test_modality_reference_passes_40_of_40"),
}


def test_docs_runner_exists_and_matches_manifest_pin() -> None:
    """The runner ships untouched (byte-pinned in docs/manifest.json).

    Manifest pins are sha256 over LF-normalized content (the git-blob form
    a CI checkout yields); a Windows autocrlf working tree is normalized
    before hashing so the pin verifies on every platform.
    """
    assert RUNNER.exists()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    pinned = manifest["hashes"][MANIFEST_RUNNER_KEY]
    normalized = RUNNER.read_bytes().replace(b"\r\n", b"\n")
    actual = hashlib.sha256(normalized).hexdigest()
    assert actual == pinned, "docs/run_post_bf_regression.py drifted from baseline"


def test_manifest_lists_only_real_repo_paths() -> None:
    """Every manifest hash entry resolves to a tracked file in the repo
    tree (R5 cleanup: zero phantom package-origin paths)."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    phantom = [p for p in manifest["hashes"] if not (REPO_ROOT / p).is_file()]
    assert not phantom, f"manifest lists non-existent paths: {phantom}"


def test_runner_layout_contradiction_is_real() -> None:
    """Both halves of the structural break, asserted as present facts:
    the behavioral tree is NOT under docs/ (runner lines 3-4 point at a
    missing tree), and the six canonical docs are NOT at the repo root
    (runner line 117 would raise FileNotFoundError from there)."""
    assert (REPO_ROOT / "behavioral_baselines").is_dir()
    assert not (DOCS_ROOT / "behavioral_baselines").exists()
    for name in (
        "PRODUCT_CONTRACT.md",
        "DOMAIN_MODEL.md",
        "STATE_MACHINES.md",
        "DATA_MODEL.md",
        "RUNTIME_ARCHITECTURE.md",
        "IMPLEMENTATION_PLAN.md",
    ):
        assert not (REPO_ROOT / name).exists(), name
        assert (DOCS_ROOT / name).is_file(), name


def test_every_behavioral_suite_is_wired_repo_native() -> None:
    """Each suite the docs runner would have replayed exists here as a
    repo-native pytest module with a real replay test — coverage by
    assertion, not by skip marker."""
    missing = []
    for suite, (module_name, test_name) in sorted(SUITE_WIRING.items()):
        module = importlib.import_module(module_name)
        test = getattr(module, test_name, None)
        if not callable(test):
            missing.append(f"{suite}: {module_name}.{test_name}")
    assert not missing, f"behavioral suites without repo-native wiring: {missing}"
