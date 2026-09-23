"""P8-1 ① — the 60-case BF-03 v1.1 benchmark, replayed in-repo.

The frozen reference (``behavioral_baselines/gate/
teaching_gate_reference_v1_1.py``) is the oracle: every case is upgraded to
the v1.1 field set **the same way** ``tests/behavioral/
test_gate_v1_1_reference.py`` does it, dispatched to the repo-native
profile that decides its ``(gate_context, authorization_path)`` pair, and
then compared to the reference's answer for the same request.

What is asserted is *agreement with the reference*, not a second copy of
the reference's implementation:

- ``execution_status`` (SUCCEEDED / DEGRADED) matches for all 60;
- the decision type matches (ALLOW / DENY / none);
- a DENY carries the reference's ``primary_reason`` and its full ``reasons``
  list, **word for word and in the same order** (the frozen precedence
  order, which this module re-derives from ``DENY_PRECEDENCE`` rather than
  trusting the comparison);
- a DEGRADED answer carries the reference's ``missing_or_unknown`` fact
  keys — the benchmark's *request* field names mapped to the §14.1 fact
  keys (the benchmark is a v1.0 artifact: its reason vocabulary says
  ``DECISION_CYCLE_INVALID`` where v1.1 says ``AUTHORIZATION_INVALID``, and
  its degraded facts are reference field names);
- an error case raises :class:`~elc.teaching.gate.GateInputError` on the
  repo-native profile exactly where the reference raises its own.

The four profiles in the dispatch table are the whole of the Gate's
implemented surface (P3-1A, P3-1B, P8-1); a case whose pair is not in the
table is a case nobody implemented, and the table's own completeness is
asserted against the benchmark's pair census instead of being assumed.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from typing import Any

import pytest

from elc.teaching.gate import (
    DENY_PRECEDENCE,
    AutoContinuationFacts,
    AutomaticOpenFacts,
    ContinuationFacts,
    GateInputError,
    UserInitiatedOpenFacts,
    decide_auto_continuation,
    decide_automatic_open,
    decide_user_initiated_open,
    decide_user_requested_continuation,
)
from tests.conftest import BASELINES

GATE_DIR = BASELINES / "gate"
EXPECTED_BENCHMARK_CASES = 60

#: The benchmark's v1.0 status word → v1.1 ``authorization_status``
#: (BF-03_Gate_v1.1_CrossLayer_Revision.md; the same table the behavioural
#: suite uses).
_STATUS_UPGRADE = {
    "VALID": "VALID",
    "STALE": "INVALIDATED",
    "INVALIDATED": "INVALIDATED",
}

#: The v1.0 → v1.1 *reason* rename of the cross-layer repair. The benchmark's
#: ``expected.primary`` still carries the v1.0 word; the reference answers
#: with the v1.1 one.
_REASON_UPGRADE = {"DECISION_CYCLE_INVALID": "AUTHORIZATION_INVALID"}

#: §14.1 fact key → the reference's request field, for the DEGRADED
#: comparison (the phase-3 differential test's map, re-declared here because
#: this suite must not import another phase's test module).
_FACT_KEY_TO_REFERENCE_FIELD = {
    "LEARNING_SNAPSHOT": "learning_snapshot",
    "AUTHORIZATION_STATUS": "authorization_status",
    "TARGET_VALIDITY": "target_status",
    "CONTENT_VALIDITY": "content_status",
    "LOCK_STATE": "lock_state",
    "SAFETY_PRIVACY_STATUS": "safety_privacy_status",
    "SUBJECT_STATUS": "subject_status",
    "GATE_STATE": "gate_state",
}


def _load_reference() -> Any:
    path = GATE_DIR / "teaching_gate_reference_v1_1.py"
    spec = importlib.util.spec_from_file_location(
        "p8_1_gate_reference_v1_1", path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.dont_write_bytecode = True  # keep the baseline tree byte-identical
    spec.loader.exec_module(module)
    return module


def _benchmark_cases() -> list[dict]:
    return json.loads(
        (GATE_DIR / "teaching_gate_benchmark_v1.json").read_text(
            encoding="utf-8"
        )
    )


def _upgrade_request(request: dict) -> dict:
    """v1.0 benchmark request → the v1.1 field set (the cross-layer repair).

    Identical in effect to ``tests/behavioral/test_gate_v1_1_reference.py``'s
    upgrade: the authorization basis by context, the status word off
    ``decision_cycle_status``, and ``continuation_requested`` for a
    user-requested continuation.
    """

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


def _facts_of(request: dict) -> object:
    """The repo-native fact bundle for one upgraded request.

    Fields the benchmark does not carry take the profile's own declared
    default; the two fields the *continuation* bundle deliberately does not
    carry (``automatic_session_budget_exhausted`` / ``hard_cooldown_active``)
    are dropped, because the reference evaluates them for new openings only
    — an AUTO_CONTINUE case that carried them would be a case about a rule
    that does not exist on that path.
    """

    context = request["gate_context"]
    intent = request["user_intent_scope"]
    if context == "OPEN":
        if request["authorization_path"] == "AUTOMATIC":
            return AutomaticOpenFacts(
                decision_cycle_id="dcy-" + request["selected_candidate_id"],
                candidate_id=request["selected_candidate_id"],
                planner_execution_status=request["planner_execution_status"],
                planner_decision=request["planner_decision"],
                proposed_action=request["proposed_action"],
                user_intent_scope=intent,
                user_initiated=request.get("user_initiated", False),
                authorization_status=request["authorization_status"],
                subject_status=request["subject_status"],
                target_status=request["target_status"],
                content_status=request["content_status"],
                safety_privacy_status=request["safety_privacy_status"],
                lock_state=request["lock_state"],
                gate_state_status=request["gate_state_status"],
                target_suppressed=request["target_suppressed"],
                automatic_teaching_enabled=request.get(
                    "automatic_teaching_enabled", True
                ),
                hard_protected_flow=request.get("hard_protected_flow", False),
                automatic_session_budget_exhausted=request.get(
                    "automatic_session_budget_exhausted", False
                ),
                hard_cooldown_active=request.get("hard_cooldown_active", False),
            )
        return UserInitiatedOpenFacts(
            decision_cycle_id="dcy-" + request["selected_candidate_id"],
            candidate_id=request["selected_candidate_id"],
            proposed_action=request["proposed_action"],
            user_intent_scope=intent,
            authorization_status=request["authorization_status"],
            subject_status=request["subject_status"],
            target_status=request["target_status"],
            content_status=request["content_status"],
            safety_privacy_status=request["safety_privacy_status"],
            lock_state=request["lock_state"],
            gate_state_status=request["gate_state_status"],
            target_suppressed=request["target_suppressed"],
        )
    if request["authorization_path"] == "AUTOMATIC":
        return AutoContinuationFacts(
            moment_id=request["moment_id"],
            proposed_action=request["proposed_action"],
            user_intent_scope=intent,
            continuation_requested=request.get(
                "continuation_requested", False
            ),
            moment_consent_class=request.get(
                "moment_consent_class", "AUTO_OPENED"
            ),
            authorization_status=request["authorization_status"],
            subject_status=request["subject_status"],
            target_status=request["target_status"],
            content_status=request["content_status"],
            safety_privacy_status=request["safety_privacy_status"],
            lock_state=request["lock_state"],
            moment_state=request["moment_state"],
            gate_state_status=request["gate_state_status"],
            target_suppressed=request["target_suppressed"],
            hard_attempt_limit_exhausted=request.get(
                "hard_attempt_limit_exhausted", False
            ),
            hard_teaching_turn_limit_exhausted=request.get(
                "hard_teaching_turn_limit_exhausted", False
            ),
            terminalizing_action=request.get("terminalizing_action", False),
            automatic_teaching_enabled=request.get(
                "automatic_teaching_enabled", True
            ),
            hard_protected_flow=request.get("hard_protected_flow", False),
        )
    return ContinuationFacts(
        moment_id=request["moment_id"],
        proposed_action=request["proposed_action"],
        user_intent_scope=intent,
        continuation_requested=request.get("continuation_requested", True),
        authorization_status=request["authorization_status"],
        subject_status=request["subject_status"],
        target_status=request["target_status"],
        content_status=request["content_status"],
        safety_privacy_status=request["safety_privacy_status"],
        lock_state=request["lock_state"],
        moment_state=request["moment_state"],
        gate_state_status=request["gate_state_status"],
        target_suppressed=request["target_suppressed"],
        hard_attempt_limit_exhausted=request.get(
            "hard_attempt_limit_exhausted", False
        ),
        hard_teaching_turn_limit_exhausted=request.get(
            "hard_teaching_turn_limit_exhausted", False
        ),
    )


_DISPATCH = {
    ("OPEN", "AUTOMATIC"): decide_automatic_open,
    ("OPEN", "USER_INITIATED"): decide_user_initiated_open,
    ("AUTO_CONTINUE", "AUTOMATIC"): decide_auto_continuation,
    ("USER_REQUESTED_CONTINUE", "USER_INITIATED"): (
        decide_user_requested_continuation
    ),
}


def _pairs() -> dict[tuple[str, str], int]:
    census: dict[tuple[str, str], int] = {}
    for case in _benchmark_cases():
        request = _upgrade_request(case["request"])
        pair = (request["gate_context"], request["authorization_path"])
        census[pair] = census.get(pair, 0) + 1
    return census


@pytest.fixture(scope="module")
def gate() -> Any:
    return _load_reference()


def test_the_benchmark_is_the_frozen_sixty() -> None:
    assert len(_benchmark_cases()) == EXPECTED_BENCHMARK_CASES


def test_every_benchmark_pair_has_a_repo_native_profile() -> None:
    """The dispatch table is the implemented Gate surface; the benchmark
    uses exactly those four pairs — so the replay below covers every case,
    and a future benchmark case with a new pair would fail here instead of
    being silently skipped."""

    census = _pairs()
    assert census == {
        ("OPEN", "AUTOMATIC"): 23,
        ("OPEN", "USER_INITIATED"): 8,
        ("AUTO_CONTINUE", "AUTOMATIC"): 18,
        ("USER_REQUESTED_CONTINUE", "USER_INITIATED"): 11,
    }
    assert set(census) == set(_DISPATCH)


def test_the_benchmark_is_still_a_v1_0_artifact() -> None:
    """The three error cases and the v1.0 reason spelling the replay has to
    translate: kept visible so the upgrade mapping is not mistaken for
    decoration."""

    cases = {case["id"]: case for case in _benchmark_cases()}
    errors = sorted(
        case["id"] for case in cases.values() if case["expected"]["error"]
    )
    assert errors == [
        "G52_NO_PLANNER_SELECT",
        "G53_WRONG_ACTION",
        "G54_USER_CONT_NO_REQUEST",
    ]
    degraded = sorted(
        case["id"] for case in cases.values() if case["expected"]["degraded"]
    )
    assert degraded == [
        "G49_UNKNOWN_SAFETY",
        "G50_UNKNOWN_LOCK",
        "G51_GATE_STATE_INCOMPLETE",
    ]
    assert cases["G55_MULTI_BLOCKERS"]["expected"]["primary"] == (
        "SAFETY_PRIVACY_BLOCK"
    )
    assert "DECISION_CYCLE_INVALID" in cases["G55_MULTI_BLOCKERS"]["expected"][
        "reasons"
    ]


def test_all_sixty_cases_agree_with_the_frozen_reference(gate: Any) -> None:
    """The judgement face: 60/60, case by case.

    A DENY's ``reasons`` is compared as the ordered tuple the profile
    returned *and* re-derived from ``DENY_PRECEDENCE``, so a profile that
    emitted the right set in the wrong order cannot pass by agreeing with
    the reference's order by accident of input.
    """

    assert _pairs()  # the census above is the completeness argument
    mismatches: list[str] = []
    #: Every case the loop actually replayed — asserted after the loop, so a
    #: case that is silently skipped (the review's m10b mutation) fails here
    #: instead of shrinking the judgement quietly.
    replayed: list[str] = []
    for case in _benchmark_cases():
        request = _upgrade_request(case["request"])
        pair = (request["gate_context"], request["authorization_path"])
        decider = _DISPATCH[pair]
        replayed.append(case["id"])
        if case["expected"]["error"]:
            # The error trio is asserted as contract errors by its own test
            # below; here they must raise on both sides and nothing else.
            with pytest.raises(GateInputError):
                decider(_facts_of(request))  # type: ignore[operator]
            continue
        theirs = gate.decide(request)
        ours = decider(_facts_of(request))  # type: ignore[operator]

        if theirs["execution_status"] != ours.execution_status:
            mismatches.append(
                f"{case['id']}: status {ours.execution_status!r} vs"
                f" {theirs['execution_status']!r}"
            )
            continue
        if theirs["decision"] is None:
            expected_keys = tuple(
                sorted(
                    _FACT_KEY_TO_REFERENCE_FIELD[key]
                    for key in ours.missing_or_unknown
                )
            )
            if ours.decision is not None or expected_keys != tuple(
                theirs["missing_or_unknown"]
            ):
                mismatches.append(
                    f"{case['id']}: degraded keys {ours.missing_or_unknown!r}"
                    f" vs {theirs['missing_or_unknown']!r}"
                )
            continue
        if theirs["decision"]["type"] != ours.decision:
            mismatches.append(
                f"{case['id']}: {ours.decision!r} vs"
                f" {theirs['decision']['type']!r}"
            )
            continue
        if ours.decision == "ALLOW":
            if theirs["decision"]["reasons"] != [] or ours.reasons != ():
                mismatches.append(f"{case['id']}: allow carried reasons")
            continue
        benchmark_reasons = case["expected"]["reasons"]
        if benchmark_reasons is None:
            # The benchmark spells the full list only where more than one
            # blocker fires; otherwise it names the primary only, and the
            # list itself is the reference's (compared above).
            expected_reasons = None
        else:
            expected_reasons = tuple(
                _REASON_UPGRADE.get(reason, reason)
                for reason in benchmark_reasons
            )
        reference_reasons = tuple(theirs["decision"]["reasons"])
        precedence_order = tuple(
            reason for reason in DENY_PRECEDENCE if reason in set(ours.reasons)
        )
        if reference_reasons != ours.reasons:
            mismatches.append(
                f"{case['id']}: reasons {ours.reasons!r} vs"
                f" {reference_reasons!r}"
            )
        elif precedence_order != ours.reasons:
            mismatches.append(
                f"{case['id']}: reasons are not in DENY_PRECEDENCE order"
            )
        elif expected_reasons is not None and expected_reasons != ours.reasons:
            mismatches.append(
                f"{case['id']}: benchmark expectation"
                f" {expected_reasons!r} vs {ours.reasons!r}"
            )
        elif _REASON_UPGRADE.get(
            case["expected"]["primary"], case["expected"]["primary"]
        ) != ours.primary_reason:
            mismatches.append(
                f"{case['id']}: primary {ours.primary_reason!r} vs benchmark"
                f" {case['expected']['primary']!r}"
            )
        elif theirs["decision"]["primary_reason"] != ours.primary_reason:
            mismatches.append(
                f"{case['id']}: primary {ours.primary_reason!r} vs"
                f" {theirs['decision']['primary_reason']!r}"
            )
    assert not mismatches, mismatches
    # Every case was judged: the loop cannot shrink silently. The ids are
    # compared as a set against the benchmark's own, so a duplicate or a
    # skip fails here rather than reducing the count below the frozen sixty.
    assert len(replayed) == EXPECTED_BENCHMARK_CASES
    assert set(replayed) == {case["id"] for case in _benchmark_cases()}


def test_error_cases_are_contract_errors_on_the_repo_native_profiles(
    gate: Any,
) -> None:
    """The three error cases: the reference raises, and so does the
    repo-native profile that decides the same pair — a program error, never
    a DECISION (BF-03 §21)."""

    seen = 0
    for case in _benchmark_cases():
        if not case["expected"]["error"]:
            continue
        seen += 1
        request = _upgrade_request(case["request"])
        with pytest.raises(gate.GateInputError):
            gate.decide(request)
        pair = (request["gate_context"], request["authorization_path"])
        with pytest.raises(GateInputError):
            _DISPATCH[pair](_facts_of(request))  # type: ignore[operator]
    assert seen == 3


def test_the_v1_0_reason_word_never_appears_in_a_v1_1_answer(
    gate: Any,
) -> None:
    """``DECISION_CYCLE_INVALID`` is the benchmark's v1.0 spelling; the
    cross-layer repair renamed it and neither implementation may answer
    with the old word (the comparison above translates the *expectation*,
    never the answer)."""

    for case in _benchmark_cases():
        request = _upgrade_request(case["request"])
        pair = (request["gate_context"], request["authorization_path"])
        decider = _DISPATCH[pair]
        if case["expected"]["error"]:
            with pytest.raises(GateInputError):
                decider(_facts_of(request))  # type: ignore[operator]
            continue
        ours = decider(_facts_of(request))  # type: ignore[operator]
        theirs = gate.decide(request)
        assert "DECISION_CYCLE_INVALID" not in ours.reasons, case["id"]
        if theirs["decision"] is not None:
            assert "DECISION_CYCLE_INVALID" not in theirs["decision"]["reasons"]
