"""VAL ⑤ (RS) — semantic equivalence: the src Estimator V1 vs the frozen
BF-01 v1.1 reference, over the golden pack and the full stress pack.

The frozen reference (behavioral_baselines/estimator/
estimator_reference_v1_1.py) is loaded as the ORACLE — importing the
baseline from tests is legal (only ``src`` is barred from
behavioral_baselines imports). Equivalence is exact deep equality of the
full output document (dimensions / coverage / freshness / projection),
not just spot fields: same structure, same rounded numbers, same flags.

Also pins:
- the golden ``expect`` semantics against the SRC output (the golden
  pack's own expectations, independently of the oracle);
- BF-01 §30 determinism (claim order permutations do not change state);
- BF-01 §25 flag vocabulary (only the allowed words can ever appear);
- BF-01 §7 strict mode (corrupted canon raises, never silently
  computes).
"""

from __future__ import annotations

import importlib.util
import itertools
import json
from pathlib import Path
from typing import Any

import pytest

from elc.learning.estimator import (
    ALLOWED_LEARNING_FLAGS,
    EstimatorClaimView,
    EstimatorContractError,
    estimate_target_state,
)
from tests.conftest import BASELINES

ESTIMATOR_DIR = BASELINES / "estimator"
GOLDEN_CASES = ESTIMATOR_DIR / "baseline_golden_cases_v1.json"
STRESS_CASES = ESTIMATOR_DIR / "estimator_stress_cases_v1_1.json"
DEFAULT_AS_OF = "2026-09-20T10:00:00+00:00"


def _load_oracle() -> Any:
    path = ESTIMATOR_DIR / "estimator_reference_v1_1.py"
    spec = importlib.util.spec_from_file_location(
        "estimator_reference_v1_1_oracle", path
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load_profile() -> dict[str, Any]:
    return json.loads(
        (ESTIMATOR_DIR / "estimator_reference_profile_v1_1.json").read_text(
            encoding="utf-8"
        )
    )


@pytest.fixture(scope="module")
def oracle() -> Any:
    return _load_oracle()


@pytest.fixture(scope="module")
def profile() -> dict[str, Any]:
    return _load_profile()


def _golden_args(case: dict[str, Any]) -> tuple[str, str, str]:
    if case["claims"]:
        first = case["claims"][0]
        return first["target_type"], first["target_id"], first["modality"]
    return "RESOURCE", "expr.test", "TEXT_PRODUCTION"


def _stress_args(case: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        case.get("tt", "RESOURCE"),
        case.get("tid", "expr.test"),
        case.get("mod", "TEXT_PRODUCTION"),
        case.get("asof", DEFAULT_AS_OF),
    )


def _src_state(
    claims: list[dict[str, Any]],
    target_type: str,
    target_id: str,
    modality: str,
    as_of: str,
) -> dict[str, Any]:
    views = [EstimatorClaimView.from_mapping(claim) for claim in claims]
    return estimate_target_state(
        views,
        target_type=target_type,
        target_id=target_id,
        modality=modality,
        as_of=as_of,
    ).as_reference_dict()


# -- exact full-document equivalence ---------------------------------------


def test_golden_pack_full_document_equivalence(
    oracle: Any, profile: dict[str, Any]
) -> None:
    cases = json.loads(GOLDEN_CASES.read_text(encoding="utf-8"))
    assert len(cases) == 10
    for case in cases:
        target_type, target_id, modality = _golden_args(case)
        reference_state = oracle.estimate(
            case["claims"],
            target_type,
            target_id,
            modality,
            DEFAULT_AS_OF,
            profile,
        )
        src_state = _src_state(
            case["claims"], target_type, target_id, modality, DEFAULT_AS_OF
        )
        assert src_state == reference_state, case["id"]


def test_stress_pack_full_document_equivalence(
    oracle: Any, profile: dict[str, Any]
) -> None:
    cases = json.loads(STRESS_CASES.read_text(encoding="utf-8"))
    assert len(cases) == 43
    for case in cases:
        target_type, target_id, modality, as_of = _stress_args(case)
        try:
            reference_state: object = oracle.estimate(
                case["claims"],
                target_type,
                target_id,
                modality,
                as_of,
                profile,
            )
            reference_error = False
        except ValueError:
            reference_state = None
            reference_error = True
        if reference_error:
            # §7 strict mode: the src estimator must refuse the same
            # corrupted input, never silently compute it.
            with pytest.raises(EstimatorContractError):
                _src_state(
                    case["claims"], target_type, target_id, modality, as_of
                )
            continue
        src_state = _src_state(
            case["claims"], target_type, target_id, modality, as_of
        )
        assert src_state == reference_state, case["id"]


# -- golden expect semantics (against SRC, independent of the oracle) ------


def _check_expect(state: dict[str, Any], expect: dict[str, Any]) -> list[str]:
    dimensions = state["dimensions"]
    projection = state["projection"]
    problems: list[str] = []
    for key, value in expect.items():
        if key == "independent_estimate":
            if dimensions["independent_production"]["estimate"] != value:
                problems.append(key)
        elif key == "independent_min":
            if not (
                dimensions["independent_production"]["estimate"] >= value
            ):
                problems.append(key)
        elif key == "independent_max":
            if not (
                dimensions["independent_production"]["estimate"] <= value
            ):
                problems.append(key)
        elif key == "spontaneous_min":
            if not (
                dimensions["spontaneous_production"]["estimate"] >= value
            ):
                problems.append(key)
        elif key == "independent_clusters":
            if (
                dimensions["independent_production"]["independent_clusters"]
                != value
            ):
                problems.append(key)
        elif key == "independent_clusters_min":
            if not (
                dimensions["independent_production"]["independent_clusters"]
                >= value
            ):
                problems.append(key)
        elif key == "confidence_band":
            if projection["confidence_band"] != value:
                problems.append(key)
        elif key == "stability_band":
            if projection["stability_band"] != value:
                problems.append(key)
        elif key == "transfer_band":
            if projection["transfer_band"] != value:
                problems.append(key)
        elif key == "ability_band":
            if projection["ability_band"] != value:
                problems.append(key)
        elif key == "transfer_known":
            known = dimensions["transfer"]["estimate"] is not None
            if known is not value:
                problems.append(key)
        elif key == "support_dependency_min":
            if not (
                dimensions["support_dependency"]["estimate"] >= value
            ):
                problems.append(key)
        elif key == "must_flag":
            if value not in projection["learning_flags"]:
                problems.append(key)
        elif key == "forbid_flags":
            for flag in value:
                if flag in projection["learning_flags"]:
                    problems.append(f"forbid:{flag}")
        elif key == "confidence_not_high":
            if projection["confidence_band"] == "HIGH":
                problems.append(key)
        elif key in {"target_type", "target_id"}:
            continue
        else:
            problems.append(f"unhandled-expect:{key}")
    return problems


def test_golden_expectations_hold_for_src() -> None:
    cases = json.loads(GOLDEN_CASES.read_text(encoding="utf-8"))
    for case in cases:
        target_type, target_id, modality = _golden_args(case)
        state = _src_state(
            case["claims"], target_type, target_id, modality, DEFAULT_AS_OF
        )
        problems = _check_expect(state, case["expect"])
        assert not problems, f"{case['id']}: {problems}"
        for flag in state["projection"]["learning_flags"]:
            assert flag in ALLOWED_LEARNING_FLAGS, (case["id"], flag)


def test_learning_flag_vocabulary_is_the_bf01_allowed_set() -> None:
    """BF-01 §25: the allowed words exactly; REVIEW_DUE / TRANSFER_NEEDED
    / TEACH_NOW / HIGH_PRIORITY can never be emitted."""
    assert ALLOWED_LEARNING_FLAGS == {
        "CONFIRMED_GAP",
        "SUPPORT_DEPENDENT",
        "CONFLICTING_EVIDENCE",
        "INSUFFICIENT_EVIDENCE",
        "NARROW_EVIDENCE",
        "STRONG_INDEPENDENT_CONTROL",
        "STRONG_SPONTANEOUS_CONTROL",
    }


# -- determinism (BF-01 §30) ------------------------------------------------


@pytest.mark.parametrize("case_id", ["E04_SAME_SESSION_REPETITION",
                                     "E05_SYSTEMATIC_FAILURE_ACROSS_DAYS",
                                     "E07_SUPPORT_DEPENDENT"])
def test_input_order_does_not_change_state(case_id: str) -> None:
    cases = json.loads(GOLDEN_CASES.read_text(encoding="utf-8"))
    case = next(c for c in cases if c["id"] == case_id)
    target_type, target_id, modality = _golden_args(case)
    claims = case["claims"]
    baseline = _src_state(
        claims, target_type, target_id, modality, DEFAULT_AS_OF
    )
    for permutation in itertools.permutations(claims):
        assert _src_state(
            list(permutation), target_type, target_id, modality, DEFAULT_AS_OF
        ) == baseline


def test_no_behavioral_baselines_import_in_src() -> None:
    """src never imports the frozen baseline assets (the reference is
    test-oracle only) — AST-scans every elc module's import face
    (docstring mentions of the baseline tree are not imports)."""
    import ast

    src_root = Path(__file__).resolve().parents[2] / "src" / "elc"
    offenders: list[str] = []
    for path in sorted(src_root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            if any(name.startswith("behavioral_baselines") for name in names):
                offenders.append(f"{path}: {names}")
    assert not offenders, offenders


# -- §7 strict mode ---------------------------------------------------------


def _claim(**overrides: Any) -> dict[str, Any]:
    claim = {
        "group_id": "g1",
        "timestamp": "2026-09-01T10:00:00+00:00",
        "performance_type": "INDEPENDENT_PRODUCTION",
        "polarity": "POSITIVE",
        "outcome": "SUCCESS",
        "evaluator_confidence": 0.95,
        "support_level": "NONE",
        "exposure_level": "NONE",
        "opportunity_type": "ELICITED",
        "qualifiers": [],
        "error_attribution": "UNKNOWN",
        "accuracy": None,
        "pragmatic_fit": None,
        "conversation_id": "c1",
        "teaching_moment_id": None,
        "persona_id": "p1",
        "context_key": "ctx1",
        "realization_key": "r1",
        "target_type": "RESOURCE",
        "target_id": "expr.test",
        "modality": "TEXT_PRODUCTION",
        "status": "ACTIVE",
        "spontaneity": None,
    }
    claim.update(overrides)
    return claim


def test_contract_violations_carry_the_spec_codes() -> None:
    from elc.learning.estimator import validate_claims

    assisted = [
        EstimatorClaimView.from_mapping(
            _claim(support_level="SEMANTIC_HINT")
        )
    ]
    codes = {v.code for v in validate_claims(assisted)}
    assert codes == {"INDEPENDENT_WITH_ASSISTANCE"}

    exposed = [
        EstimatorClaimView.from_mapping(_claim(exposure_level="FULL"))
    ]
    codes = {v.code for v in validate_claims(exposed)}
    assert codes == {"INDEPENDENT_WITH_ANSWER_EXPOSURE"}

    unnatural = [
        EstimatorClaimView.from_mapping(
            _claim(
                performance_type="SPONTANEOUS_PRODUCTION",
                opportunity_type="ELICITED",
            )
        )
    ]
    codes = {v.code for v in validate_claims(unnatural)}
    assert codes == {"SPONTANEOUS_REQUIRES_NATURAL_OPPORTUNITY"}

    duplicated_primary = [
        EstimatorClaimView.from_mapping(
            _claim(performance_type="FAILED_ATTEMPT", polarity="NEGATIVE",
                   outcome="FAILURE")
        ),
        EstimatorClaimView.from_mapping(
            _claim(performance_type="GUIDED_PRODUCTION")
        ),
    ]
    codes = {v.code for v in validate_claims(duplicated_primary)}
    assert codes == {"MULTIPLE_PRIMARY_PERFORMANCE_SAME_GROUP_TARGET"}

    # §7.2: the same behavior MAY target multiple different targets.
    multi_target = [
        EstimatorClaimView.from_mapping(_claim(target_id="expr.a")),
        EstimatorClaimView.from_mapping(_claim(target_id="expr.b")),
    ]
    assert validate_claims(multi_target) == ()


def test_strict_mode_raises_and_loose_mode_computes() -> None:
    claims = [
        EstimatorClaimView.from_mapping(
            _claim(support_level="SEMANTIC_HINT")
        )
    ]
    with pytest.raises(EstimatorContractError):
        estimate_target_state(
            claims,
            target_type="RESOURCE",
            target_id="expr.test",
            modality="TEXT_PRODUCTION",
            as_of=DEFAULT_AS_OF,
        )
    # Loose mode is diagnostic-only and computes past the violation.
    state = estimate_target_state(
        claims,
        target_type="RESOURCE",
        target_id="expr.test",
        modality="TEXT_PRODUCTION",
        as_of=DEFAULT_AS_OF,
        strict=False,
    )
    assert state.projection.ability_band == "INDEPENDENT"
