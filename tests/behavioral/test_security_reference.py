"""Behavioral baseline wiring — Security/Privacy/Deletion reference (BF-05).

Replays behavioral_baselines/security/security_reference_v1.py AS-IS
(loaded from its pinned file, never modified) against the 61-case benchmark
security_benchmark_v1.json under the committed policy
security_privacy_policy_v1.json. The case-dispatch and expectation checks
are ported from the record section of docs/run_post_bf_regression.py so the
repo-native suite and the packaged runner judge identical semantics:

- log cases: `contains` substring checks plus field equality;
- deletion cases: must_delete / must_rebuild / must_cancel / must_tombstone
  / must_keep membership;
- import cases: id-sequence equality;
- everything else: flat field equality on the returned mapping.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from typing import Any

from tests.conftest import BASELINES

SECURITY_DIR = BASELINES / "security"
EXPECTED_CASES = 61


def _load_reference() -> Any:
    path = SECURITY_DIR / "security_reference_v1.py"
    spec = importlib.util.spec_from_file_location("security_reference_v1", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.dont_write_bytecode = True  # keep the baseline tree byte-identical
    spec.loader.exec_module(module)
    return module


def _cases() -> list[dict]:
    return json.loads(
        (SECURITY_DIR / "security_benchmark_v1.json").read_text(encoding="utf-8")
    )


def _contains_value(obj: Any, val: Any) -> bool:
    if obj == val:
        return True
    if isinstance(obj, dict):
        return any(_contains_value(v, val) for v in obj.values())
    if isinstance(obj, list):
        return any(_contains_value(v, val) for v in obj)
    if isinstance(obj, str):
        return val in obj
    return False


def _run_case(sec: Any, policy: dict, case: dict) -> bool:
    category = case["category"]
    payload = case["input"]
    expected = case["expected"]
    if category == "memory_write":
        result = sec.authorize_memory_write(payload)
    elif category == "provider":
        result = sec.authorize_provider_disclosure(
            payload["action"], payload["views"], policy
        )
    elif category == "log":
        result = sec.sanitize_log(payload["event"])
    elif category == "export":
        result = sec.plan_export(payload["records"])
    elif category == "deletion":
        result = sec.plan_deletion(payload["request"], payload["graph"])
    elif category == "import":
        result = sec.import_with_tombstones(payload["records"], payload["tombstones"])
    elif category == "endpoint":
        result = sec.validate_provider_endpoint(payload["url"])
    elif category == "external_delete":
        result = sec.plan_external_disclosure_deletion(payload["disclosure"])
    elif category == "provider_action":
        result = sec.validate_provider_action(payload["action"])
    else:
        raise AssertionError(f"unknown security category: {category}")

    if category == "log":
        for key, value in expected.items():
            if key == "contains":
                if not _contains_value(result, value):
                    return False
            elif result.get(key) != value:
                return False
        return True
    if category == "deletion":
        for item in expected.get("must_delete", []):
            if item not in result["delete"]:
                return False
        for item in expected.get("must_rebuild", []):
            if item not in result["rebuild"]:
                return False
        for item in expected.get("must_cancel", []):
            if item not in result["cancel"]:
                return False
        for item in expected.get("must_tombstone", []):
            if item not in result["tombstones"]:
                return False
        for item in expected.get("must_keep", []):
            if item in result["delete"]:
                return False
        return True
    if category == "import":
        return [z["id"] for z in result] == expected["ids"]
    return all(result.get(k) == v for k, v in expected.items())


def test_security_benchmark_case_count_is_baseline() -> None:
    assert len(_cases()) == EXPECTED_CASES


def test_security_reference_passes_61_of_61() -> None:
    sec = _load_reference()
    policy = json.loads(
        (SECURITY_DIR / "security_privacy_policy_v1.json").read_text(encoding="utf-8")
    )
    failures: list[str] = []
    passed = 0
    for case in _cases():
        try:
            ok = _run_case(sec, policy, case)
        except Exception as exc:  # noqa: BLE001 - record the failing case verbatim
            failures.append(f"{case['id']}: raised {exc!r}")
            continue
        if ok:
            passed += 1
        else:
            failures.append(f"{case['id']}: expectation not met")
    assert not failures, failures
    assert passed == EXPECTED_CASES
