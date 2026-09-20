"""Behavioral baseline wiring — Modality Scope reference (BF-06).

Replays behavioral_baselines/modality/modality_scope_reference_v1.py AS-IS
(loaded from its pinned file, never modified) against the 40-case benchmark
modality_benchmark_v1.json under the committed policy
modality_scope_policy_v1.json. The case dispatch and expectation checks are
ported line-for-line from the record section of
docs/run_post_bf_regression.py, including the future-runtime projection
(voice input + pronunciation/speaking-fluency/listening evaluators enabled)
used by the *_future case classes.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from typing import Any

from tests.conftest import BASELINES

MODALITY_DIR = BASELINES / "modality"
EXPECTED_CASES = 40


def _load_reference() -> Any:
    path = MODALITY_DIR / "modality_scope_reference_v1.py"
    spec = importlib.util.spec_from_file_location("modality_scope_reference_v1", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.dont_write_bytecode = True  # keep the baseline tree byte-identical
    spec.loader.exec_module(module)
    return module


def _policy() -> dict:
    return json.loads(
        (MODALITY_DIR / "modality_scope_policy_v1.json").read_text(encoding="utf-8")
    )


def _cases() -> list[dict]:
    return json.loads(
        (MODALITY_DIR / "modality_benchmark_v1.json").read_text(encoding="utf-8")
    )


def _runtimes(policy: dict) -> dict[str, dict]:
    future = {
        **policy["v1_runtime_capabilities"],
        "voice_input": True,
        "pronunciation_evaluator": True,
        "speaking_fluency_evaluator": True,
        "listening_comprehension_evaluator": True,
    }
    return {"v1": policy["v1_runtime_capabilities"], "future": future}


def _run_case(mod: Any, policy: dict, runtimes: dict[str, dict], case: dict) -> bool:
    category = case["category"]
    payload = case["input"]
    expected = case["expected"]
    if category in {"classify", "classify_future"}:
        runtime = runtimes["v1" if category == "classify" else "future"]
        result = mod.classify_observation(payload, runtime)
        return all(result.get(k) == v for k, v in expected.items())
    if category == "relation":
        result = mod.goal_relation(
            payload["evidence_modality"],
            payload["goal_modality"],
            payload["task_contract"],
            policy,
        )
        return result == expected["relation"]
    if category == "dims":
        runtime = runtimes[payload.get("runtime", "v1")]
        dims = set(
            mod.allowed_measurement_dimensions(payload["evidence_modality"], runtime)
        )
        return all(v in dims for v in expected.get("allow", [])) and all(
            v not in dims for v in expected.get("forbid", [])
        )
    if category in {"claim", "claim_future"}:
        runtime = runtimes["v1" if category == "claim" else "future"]
        result = mod.can_claim(
            payload["claim_kind"],
            payload["evidence_modalities"],
            runtime,
            payload.get("validated_assessment_module", False),
        )
        return result == expected["allowed"]
    if category == "coverage":
        runtime = runtimes[payload["runtime"]]
        result = mod.coverage_obligation(payload["goal_modality"], runtime)
        return all(result.get(k) == v for k, v in expected.items())
    if category == "state_key":
        result = list(
            mod.canonical_state_key(
                payload["target_type"],
                payload["target_id"],
                payload["evidence_modality"],
            )
        )
        return result == expected["key"]
    raise AssertionError(f"unknown modality category: {category}")


def test_modality_benchmark_case_count_is_baseline() -> None:
    assert len(_cases()) == EXPECTED_CASES


def test_modality_reference_passes_40_of_40() -> None:
    mod = _load_reference()
    policy = _policy()
    runtimes = _runtimes(policy)
    failures: list[str] = []
    passed = 0
    for case in _cases():
        try:
            ok = _run_case(mod, policy, runtimes, case)
        except Exception as exc:  # noqa: BLE001 - record the failing case verbatim
            failures.append(f"{case['id']}: raised {exc!r}")
            continue
        if ok:
            passed += 1
        else:
            failures.append(f"{case['id']}: expectation not met")
    assert not failures, failures
    assert passed == EXPECTED_CASES
