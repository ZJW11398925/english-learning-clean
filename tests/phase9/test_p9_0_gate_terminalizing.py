"""P9-0 (B) — ``ContinuationFacts.terminalizing_action`` (p8-1's F11).

The frozen reference reads ``terminalizing_action`` in **both** continuation
contexts — its ``terminalizing`` line is not branched on ``gate_context`` —
but until this cut only :class:`AutoContinuationFacts` carried the field, so
the reference's §8 exemption (a terminalizing move is never blocked by the
teaching-turn cap) was unreachable on the ``USER_REQUESTED_CONTINUE``
profile. The 60-case benchmark could not see the gap: all eleven of its cases
in that context carry ``terminalizing_action = False``.

What is pinned here: the field's shape (same place, same default, same
semantics as the automatic bundle's), the two arms that make it reachable
(``True`` ⇒ ALLOW, ``False`` ⇒ DENY on the same hard cap), the invariance of
the word class (a ``REVEAL`` needs no flag) and of the retry-like half (it is
derived from the word, not carried), the agreement with the frozen reference
on both arms, and the benchmark's own data claim (all eleven cases ``False``,
so the replay cannot regress).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import fields, replace
from pathlib import Path
from typing import Any

import pytest

from elc.teaching.gate import (
    AutoContinuationFacts,
    ContinuationFacts,
    decide_auto_continuation,
    decide_user_requested_continuation,
)
from tests.conftest import BASELINES

BENCHMARK = BASELINES / "gate" / "teaching_gate_benchmark_v1.json"
REFERENCE = BASELINES / "gate" / "teaching_gate_reference_v1_1.py"

CONTEXT = "USER_REQUESTED_CONTINUE"


def _load_reference() -> Any:
    spec = importlib.util.spec_from_file_location(
        "p9_0_gate_reference_v1_1", REFERENCE
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.dont_write_bytecode = True  # keep the baseline tree byte-identical
    spec.loader.exec_module(module)
    return module


def _facts(**overrides: object) -> ContinuationFacts:
    """One otherwise-healthy USER_REQUESTED_CONTINUE bundle."""

    return ContinuationFacts(moment_id="tm-p9-0", **overrides)  # type: ignore[arg-type]


def _request(**overrides: object) -> dict[str, Any]:
    """The same bundle as the reference's own request dict."""

    request: dict[str, Any] = {
        "gate_context": CONTEXT,
        "authorization_path": "USER_INITIATED",
        "authorization_basis": "ACTIVE_MOMENT",
        "moment_id": "tm-p9-0",
        "user_initiated": True,
        "proposed_action": "HINT",
        "user_intent_scope": "ACTIVE_TEACHING_CONTINUATION",
        "continuation_requested": True,
        "authorization_status": "VALID",
        "subject_status": "ACTIVE",
        "target_status": "VALID",
        "content_status": "VALID",
        "lock_state": "OWNED_BY_THIS_MOMENT",
        "moment_state": "DECIDING_NEXT_ACTION",
        "gate_state_status": "COMPLETE",
        "safety_privacy_status": "ALLOW",
        "target_suppressed": False,
        "hard_attempt_limit_exhausted": False,
        "hard_teaching_turn_limit_exhausted": False,
        "terminalizing_action": False,
    }
    request.update(overrides)
    return request


# -- ① the field's shape -----------------------------------------------------


def test_the_field_is_where_the_automatic_bundles_is() -> None:
    """Same name, same position, same default — the shape p8-1's carryover
    named ("按 ``AutoContinuationFacts`` 同形补字段"): directly after the two
    §8 hard caps in both bundles, and defaulting to ``False``."""

    user_fields = [field.name for field in fields(ContinuationFacts)]
    auto_fields = [field.name for field in fields(AutoContinuationFacts)]
    for names in (user_fields, auto_fields):
        assert names.index("terminalizing_action") == (
            names.index("hard_teaching_turn_limit_exhausted") + 1
        )
    default = next(
        field
        for field in fields(ContinuationFacts)
        if field.name == "terminalizing_action"
    )
    assert default.default is False
    assert replace(_facts()).terminalizing_action is False


def test_the_word_class_is_not_restated_from_the_flag() -> None:
    """A ``REVEAL`` is terminalizing on its own word: the flag can only add,
    never subtract — a bundle whose word is terminalizing needs no flag, and
    the word's own class is what the reference reads there."""

    reveal = _facts(
        proposed_action="REVEAL",
        hard_teaching_turn_limit_exhausted=True,
    )
    verdict = decide_user_requested_continuation(reveal)
    assert verdict.decision == "ALLOW"
    assert verdict.reasons == ()


# -- ② the two arms ----------------------------------------------------------


def test_a_terminalizing_move_is_exempt_from_the_teaching_turn_cap() -> None:
    """The gap p8-1's F11 recorded: ``hard_teaching_turn_limit_exhausted``
    with a ``HINT`` word, and the reference's own fact saying the move is
    terminalizing — ALLOW (the §8 exemption)."""

    facts = _facts(
        proposed_action="HINT",
        hard_teaching_turn_limit_exhausted=True,
        terminalizing_action=True,
    )
    verdict = decide_user_requested_continuation(facts)
    assert verdict.execution_status == "SUCCEEDED"
    assert verdict.decision == "ALLOW"
    assert verdict.primary_reason is None
    assert verdict.reasons == ()


def test_the_same_bundle_without_the_flag_is_denied() -> None:
    """The control: the same hard cap and the same word, with the flag
    ``False`` — the teaching-turn cap fires, so the flag is what decides the
    two arms rather than the word alone."""

    facts = _facts(
        proposed_action="HINT",
        hard_teaching_turn_limit_exhausted=True,
        terminalizing_action=False,
    )
    verdict = decide_user_requested_continuation(facts)
    assert verdict.decision == "DENY"
    assert verdict.primary_reason == "HARD_TEACHING_TURN_LIMIT"
    assert verdict.reasons == ("HARD_TEACHING_TURN_LIMIT",)


def test_the_attempt_cap_keeps_its_retry_like_half() -> None:
    """The other half of §8's classification is derived from the word, not
    carried: a retry-like move under the attempt cap is denied, and the flag
    does not exempt it (the reference's ``retry_like`` line reads only the
    action word)."""

    denied = _facts(
        proposed_action="HINT",
        hard_attempt_limit_exhausted=True,
        terminalizing_action=True,
    )
    assert decide_user_requested_continuation(denied).primary_reason == (
        "HARD_ATTEMPT_LIMIT"
    )
    reveal = _facts(
        proposed_action="REVEAL",
        hard_attempt_limit_exhausted=True,
        terminalizing_action=True,
    )
    assert decide_user_requested_continuation(reveal).decision == "ALLOW"


# -- ③ the frozen reference agrees on both arms ------------------------------


@pytest.mark.parametrize(
    ("proposed_action", "turn_cap", "flag"),
    [
        ("HINT", True, True),
        ("HINT", True, False),
        ("HINT", False, True),
        ("REVEAL", True, False),
        ("TERMINAL_FEEDBACK", True, False),
        ("RETRY", True, True),
    ],
)
def test_both_arms_are_the_frozen_references_verdict(
    proposed_action: str, turn_cap: bool, flag: bool
) -> None:
    """The reference is executable and it is not imported by shipping code;
    running it beside the profile is how "the flag is read the way the
    reference reads it" is checked rather than asserted from memory."""

    reference = _load_reference()
    request = _request(
        proposed_action=proposed_action,
        hard_teaching_turn_limit_exhausted=turn_cap,
        terminalizing_action=flag,
    )
    theirs = reference.decide(request)
    ours = decide_user_requested_continuation(
        _facts(
            proposed_action=proposed_action,
            hard_teaching_turn_limit_exhausted=turn_cap,
            terminalizing_action=flag,
        )
    )
    assert ours.execution_status == theirs["execution_status"]
    assert ours.decision == theirs["decision"]["type"]
    if ours.decision == "DENY":
        assert ours.primary_reason == theirs["decision"]["primary_reason"]
        assert ours.reasons == tuple(theirs["decision"]["reasons"])


def test_the_automatic_bundle_is_untouched() -> None:
    """The control for the whole cut: the profile that always had the field
    behaves exactly as it did (the same two arms), so the repair added a
    reading to one profile and changed none."""

    facts = AutoContinuationFacts(
        moment_id="tm-p9-0",
        proposed_action="HINT",
        hard_teaching_turn_limit_exhausted=True,
        terminalizing_action=True,
    )
    assert decide_auto_continuation(facts).decision == "ALLOW"
    denied = replace(facts, terminalizing_action=False)
    assert decide_auto_continuation(denied).primary_reason == (
        "HARD_TEACHING_TURN_LIMIT"
    )


# -- ④ the benchmark's own claim ---------------------------------------------


def test_the_benchmark_cannot_have_regressed_in_this_context() -> None:
    """The measured reason the 60-case replay stays green: every one of its
    eleven ``USER_REQUESTED_CONTINUE`` cases carries the field and every one
    carries ``False`` — so the profile's new reading returns exactly the
    verdict the old code returned for those cases. (The replay itself is
    tests/phase8/test_p8_1_gate_benchmark_replay.py's; this file pins the data
    the claim rests on.)"""

    cases = json.loads(Path(BENCHMARK).read_text(encoding="utf-8"))
    in_context = [
        case for case in cases if case["request"]["gate_context"] == CONTEXT
    ]
    assert len(in_context) == 11
    assert all("terminalizing_action" in case["request"] for case in in_context)
    assert {
        case["request"]["terminalizing_action"] for case in in_context
    } == {False}
    assert len(cases) == 60
