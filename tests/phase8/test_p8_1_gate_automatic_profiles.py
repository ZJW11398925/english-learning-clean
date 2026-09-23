"""P8-1 ② — the two AUTOMATIC Gate profiles, contract and behaviour.

The 60-case agreement lives in
``test_p8_1_gate_benchmark_replay.py``; this suite pins the profiles
*themselves* — what each one may emit, what it refuses, and the four
asymmetries the frozen reference carries on purpose:

- the automatic controls (auto-teach preference, session budget, cooldown)
  guard **new automatic openings only** — an in-flight continuation is not
  stopped by a budget that ran out mid-moment;
- the flow protection fires on ``(OPEN ∧ AUTOMATIC) or AUTO_CONTINUE`` and
  is bypassed by a user-requested continuation (BF-03 §12);
- the auto-teach preference blocks an ``AUTO_OPENED`` continuation and not
  a ``USER_AUTHORIZED`` one (BF-03 §17);
- critical-fact incompleteness degrades **before** any deterministic
  blocker is considered (never a synthetic DENY).
"""

from __future__ import annotations

import dataclasses
from dataclasses import replace
from typing import Any

import pytest

from elc.teaching.gate import (
    AUTO_CONTINUATION_FACT_KEYS,
    AUTO_CONTINUATION_REASON_CODES,
    AUTOMATIC_OPEN_FACT_KEYS,
    AUTOMATIC_OPEN_REASON_CODES,
    DENY_PRECEDENCE,
    MISSING_OR_UNKNOWN_FACT_KEYS,
    USER_INITIATED_CONTINUATION_INTENTS,
    AutoContinuationFacts,
    AutomaticOpenFacts,
    GateInputError,
    decide_auto_continuation,
    decide_automatic_open,
    moment_consent_class_of,
)


def _open_facts(**overrides: Any) -> AutomaticOpenFacts:
    return replace(
        AutomaticOpenFacts(
            decision_cycle_id="dcy-p8-1", candidate_id="cand-p8-1"
        ),
        **overrides,
    )


def _continuation_facts(**overrides: Any) -> AutoContinuationFacts:
    return replace(AutoContinuationFacts(moment_id="tm-p8-1"), **overrides)


# ---------------------------------------------------------------------------
# vocabulary
# ---------------------------------------------------------------------------


def test_automatic_open_fact_keys_are_the_opening_eight() -> None:
    assert AUTOMATIC_OPEN_FACT_KEYS == MISSING_OR_UNKNOWN_FACT_KEYS


def test_auto_continuation_fact_keys_are_the_continuation_seven() -> None:
    assert AUTO_CONTINUATION_FACT_KEYS == tuple(
        key for key in MISSING_OR_UNKNOWN_FACT_KEYS if key != "LEARNING_SNAPSHOT"
    )


def test_automatic_open_reason_codes_are_the_open_subset_in_precedence() -> None:
    assert AUTOMATIC_OPEN_REASON_CODES == (
        "SAFETY_PRIVACY_BLOCK",
        "ACTION_CANCELLED",
        "ACTION_SUPERSEDED",
        "AUTHORIZATION_INVALID",
        "TARGET_INVALID",
        "CONTENT_INVALID",
        "TARGET_SUPPRESSED",
        "USER_INTENT_BLOCK",
        "AUTO_TEACH_DISABLED",
        "TEACHING_LOCK_CONFLICT",
        "HARD_PROTECTED_FLOW",
        "AUTO_SESSION_BUDGET_EXHAUSTED",
        "HARD_COOLDOWN_ACTIVE",
    )
    for code in (
        "TEACHING_LOCK_INVALID",
        "MOMENT_NOT_CONTINUABLE",
        "HARD_ATTEMPT_LIMIT",
        "HARD_TEACHING_TURN_LIMIT",
    ):
        assert code not in AUTOMATIC_OPEN_REASON_CODES
        assert code in DENY_PRECEDENCE  # still frozen vocabulary


def test_auto_continuation_reason_codes_are_the_continuation_subset() -> None:
    assert AUTO_CONTINUATION_REASON_CODES == (
        "SAFETY_PRIVACY_BLOCK",
        "ACTION_CANCELLED",
        "ACTION_SUPERSEDED",
        "AUTHORIZATION_INVALID",
        "TARGET_INVALID",
        "CONTENT_INVALID",
        "TARGET_SUPPRESSED",
        "USER_INTENT_BLOCK",
        "AUTO_TEACH_DISABLED",
        "TEACHING_LOCK_CONFLICT",
        "TEACHING_LOCK_INVALID",
        "MOMENT_NOT_CONTINUABLE",
        "HARD_PROTECTED_FLOW",
        "HARD_ATTEMPT_LIMIT",
        "HARD_TEACHING_TURN_LIMIT",
    )
    # The two automatic opening controls are absent on purpose: the frozen
    # reference evaluates them for new openings only.
    for code in (
        "AUTO_SESSION_BUDGET_EXHAUSTED",
        "HARD_COOLDOWN_ACTIVE",
    ):
        assert code not in AUTO_CONTINUATION_REASON_CODES
        assert code in DENY_PRECEDENCE


def test_every_declared_reason_code_is_reachable() -> None:
    """Each code in the two declared sets is produced by the profile it
    belongs to — the sets are not a hopeful superset."""

    produced_open = {
        decide_automatic_open(_open_facts(**case)).reasons[0]
        for case in (
            {"safety_privacy_status": "BLOCK"},
            {"subject_status": "CANCELLED"},
            {"subject_status": "SUPERSEDED"},
            {"authorization_status": "INVALIDATED"},
            {"target_status": "INVALID"},
            {"content_status": "INVALID"},
            {"target_suppressed": True},
            {"user_intent_scope": "JUST_CHAT"},
            {"automatic_teaching_enabled": False},
            {"lock_state": "OWNED_BY_OTHER"},
            {"hard_protected_flow": True},
            {"automatic_session_budget_exhausted": True},
            {"hard_cooldown_active": True},
        )
    }
    assert produced_open == set(AUTOMATIC_OPEN_REASON_CODES)

    produced_continuation = {
        decide_auto_continuation(_continuation_facts(**case)).reasons[0]
        for case in (
            {"safety_privacy_status": "BLOCK"},
            {"subject_status": "CANCELLED"},
            {"subject_status": "SUPERSEDED"},
            {"authorization_status": "INVALIDATED"},
            {"target_status": "INVALID"},
            {"content_status": "INVALID"},
            {"target_suppressed": True},
            {"user_intent_scope": "JUST_CHAT"},
            {"automatic_teaching_enabled": False},
            {"lock_state": "OWNED_BY_OTHER"},
            {"lock_state": "NONE"},
            {"moment_state": "AWAITING_USER"},
            {"hard_protected_flow": True},
            {"hard_attempt_limit_exhausted": True, "proposed_action": "RETRY"},
            {"hard_teaching_turn_limit_exhausted": True},
        )
    }
    assert produced_continuation == set(AUTO_CONTINUATION_REASON_CODES)


# ---------------------------------------------------------------------------
# AUTOMATIC OPEN — behaviour
# ---------------------------------------------------------------------------


def test_clean_automatic_open_allows() -> None:
    verdict = decide_automatic_open(_open_facts())
    assert verdict.execution_status == "SUCCEEDED"
    assert verdict.decision == "ALLOW"
    assert verdict.reasons == ()
    assert verdict.missing_or_unknown == ()


def test_automatic_open_checks_its_own_path_and_context() -> None:
    with pytest.raises(GateInputError):
        decide_automatic_open(
            replace(_open_facts(), authorization_path="USER_INITIATED")
        )
    with pytest.raises(GateInputError):
        decide_automatic_open(
            replace(_open_facts(), gate_context="AUTO_CONTINUE")
        )
    with pytest.raises(GateInputError):
        decide_automatic_open(replace(_open_facts(), user_initiated=True))


def test_automatic_open_needs_the_planner_facts_it_consumes() -> None:
    """The profile never invents a selection: a run that did not succeed, a
    run that did not select, an empty candidate, and a bundle that claims
    the user asked are refusals (BF-03 §3/§21)."""

    for bad in (
        {"planner_execution_status": "DEGRADED"},
        {"planner_decision": "NO_TARGET"},
        {"candidate_id": ""},
        {"decision_cycle_id": ""},
        {"proposed_action": "HINT"},
        {"authorization_basis": "ACTIVE_MOMENT"},
        {"moment_id": "tm-already-here"},
        {"user_initiated": True},
    ):
        with pytest.raises(GateInputError):
            decide_automatic_open(_open_facts(**bad))


def test_automatic_open_treats_an_unknown_snapshot_as_degrading() -> None:
    """The repo-native LEARNING_SNAPSHOT fact belongs to the opening
    profiles: an unknown snapshot degrades the automatic opening exactly as
    it degrades the user-initiated one."""

    verdict = decide_automatic_open(
        _open_facts(learning_snapshot_status="UNKNOWN")
    )
    assert verdict.execution_status == "DEGRADED"
    assert verdict.decision is None
    assert verdict.missing_or_unknown == ("LEARNING_SNAPSHOT",)


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"safety_privacy_status": "BLOCK"}, "SAFETY_PRIVACY_BLOCK"),
        ({"subject_status": "CANCELLED"}, "ACTION_CANCELLED"),
        ({"subject_status": "SUPERSEDED"}, "ACTION_SUPERSEDED"),
        ({"authorization_status": "INVALIDATED"}, "AUTHORIZATION_INVALID"),
        ({"target_status": "INVALID"}, "TARGET_INVALID"),
        ({"target_status": "DEPRECATED"}, "TARGET_INVALID"),
        ({"target_status": "MISSING"}, "TARGET_INVALID"),
        ({"content_status": "INVALID"}, "CONTENT_INVALID"),
        ({"target_suppressed": True}, "TARGET_SUPPRESSED"),
        ({"user_intent_scope": "JUST_CHAT"}, "USER_INTENT_BLOCK"),
        ({"user_intent_scope": "NON_LEARNING_TASK"}, "USER_INTENT_BLOCK"),
        ({"automatic_teaching_enabled": False}, "AUTO_TEACH_DISABLED"),
        ({"lock_state": "OWNED_BY_OTHER"}, "TEACHING_LOCK_CONFLICT"),
        ({"lock_state": "OWNED_BY_THIS_MOMENT"}, "TEACHING_LOCK_CONFLICT"),
        ({"hard_protected_flow": True}, "HARD_PROTECTED_FLOW"),
        (
            {"automatic_session_budget_exhausted": True},
            "AUTO_SESSION_BUDGET_EXHAUSTED",
        ),
        ({"hard_cooldown_active": True}, "HARD_COOLDOWN_ACTIVE"),
    ],
)
def test_each_automatic_open_check_family_denies_with_its_code(
    overrides: dict[str, Any], expected: str
) -> None:
    verdict = decide_automatic_open(_open_facts(**overrides))
    assert verdict.decision == "DENY"
    assert verdict.primary_reason == expected
    assert verdict.reasons[0] == expected


def test_automatic_open_orders_overlapping_reasons_by_precedence() -> None:
    verdict = decide_automatic_open(
        _open_facts(
            hard_cooldown_active=True,
            automatic_session_budget_exhausted=True,
            hard_protected_flow=True,
            automatic_teaching_enabled=False,
            target_suppressed=True,
            target_status="INVALID",
        )
    )
    assert verdict.primary_reason == "TARGET_INVALID"
    assert verdict.reasons == (
        "TARGET_INVALID",
        "TARGET_SUPPRESSED",
        "AUTO_TEACH_DISABLED",
        "HARD_PROTECTED_FLOW",
        "AUTO_SESSION_BUDGET_EXHAUSTED",
        "HARD_COOLDOWN_ACTIVE",
    )


@pytest.mark.parametrize(
    ("overrides", "fact_key"),
    [
        ({"learning_snapshot_status": "UNKNOWN"}, "LEARNING_SNAPSHOT"),
        ({"authorization_status": "UNKNOWN"}, "AUTHORIZATION_STATUS"),
        ({"target_status": "UNKNOWN"}, "TARGET_VALIDITY"),
        ({"content_status": "UNKNOWN"}, "CONTENT_VALIDITY"),
        ({"lock_state": "UNKNOWN"}, "LOCK_STATE"),
        ({"safety_privacy_status": "UNKNOWN"}, "SAFETY_PRIVACY_STATUS"),
        ({"subject_status": "UNKNOWN"}, "SUBJECT_STATUS"),
        ({"gate_state_status": "INCOMPLETE"}, "GATE_STATE"),
    ],
)
def test_each_automatic_open_unknown_degrades_with_its_fact_key(
    overrides: dict[str, Any], fact_key: str
) -> None:
    verdict = decide_automatic_open(_open_facts(**overrides))
    assert verdict.execution_status == "DEGRADED"
    assert verdict.decision is None
    assert verdict.missing_or_unknown == (fact_key,)


def test_automatic_open_unknown_beats_a_deterministic_blocker() -> None:
    verdict = decide_automatic_open(
        _open_facts(
            lock_state="UNKNOWN",
            automatic_teaching_enabled=False,
            hard_cooldown_active=True,
        )
    )
    assert verdict.execution_status == "DEGRADED"
    assert verdict.decision is None


def test_automatic_open_rejects_an_unknown_vocabulary_word() -> None:
    for bad in (
        {"lock_state": "BROKEN"},
        {"target_status": "BROKEN"},
        {"content_status": "BROKEN"},
        {"authorization_status": "BROKEN"},
        {"subject_status": "BROKEN"},
        {"safety_privacy_status": "BROKEN"},
        {"gate_state_status": "BROKEN"},
        {"learning_snapshot_status": "BROKEN"},
        {"user_intent_scope": "NOT_A_SCOPE"},
    ):
        with pytest.raises(GateInputError):
            decide_automatic_open(_open_facts(**bad))


# ---------------------------------------------------------------------------
# AUTO_CONTINUE — behaviour
# ---------------------------------------------------------------------------


def test_clean_auto_continuation_allows() -> None:
    verdict = decide_auto_continuation(_continuation_facts())
    assert verdict.execution_status == "SUCCEEDED"
    assert verdict.decision == "ALLOW"
    assert verdict.reasons == ()


def test_auto_continuation_checks_its_own_path_and_context() -> None:
    with pytest.raises(GateInputError):
        decide_auto_continuation(
            replace(_continuation_facts(), gate_context="USER_REQUESTED_CONTINUE")
        )
    with pytest.raises(GateInputError):
        decide_auto_continuation(
            replace(_continuation_facts(), authorization_path="USER_INITIATED")
        )
    with pytest.raises(GateInputError):
        decide_auto_continuation(
            replace(_continuation_facts(), authorization_basis="DECISION_CYCLE")
        )
    with pytest.raises(GateInputError):
        decide_auto_continuation(
            replace(_continuation_facts(), proposed_action="OPENING")
        )
    with pytest.raises(GateInputError):
        decide_auto_continuation(replace(_continuation_facts(), moment_id=""))


def test_auto_continuation_cannot_claim_the_user_asked() -> None:
    """The frozen reference's "AUTO_CONTINUE cannot claim
    continuation_requested": a contract error, never a DENY."""

    with pytest.raises(GateInputError):
        decide_auto_continuation(
            replace(_continuation_facts(), continuation_requested=True)
        )


def test_auto_continuation_rejects_an_unknown_consent_class() -> None:
    with pytest.raises(GateInputError):
        decide_auto_continuation(
            replace(_continuation_facts(), moment_consent_class="GUESSED")
        )


def test_auto_continuation_loses_the_lock_two_ways() -> None:
    conflict = decide_auto_continuation(
        _continuation_facts(lock_state="OWNED_BY_OTHER")
    )
    assert conflict.primary_reason == "TEACHING_LOCK_CONFLICT"
    invalid = decide_auto_continuation(
        _continuation_facts(lock_state="NONE")
    )
    assert invalid.primary_reason == "TEACHING_LOCK_INVALID"


def test_auto_continuation_needs_a_deciding_moment() -> None:
    verdict = decide_auto_continuation(
        _continuation_facts(moment_state="AWAITING_USER")
    )
    assert verdict.primary_reason == "MOMENT_NOT_CONTINUABLE"


def test_auto_continuation_ignores_the_intent_scope_of_a_changed_topic() -> None:
    verdict = decide_auto_continuation(
        _continuation_facts(user_intent_scope="NON_LEARNING_TASK")
    )
    assert verdict.reasons == ("USER_INTENT_BLOCK",)


def test_the_automatic_controls_do_not_stop_a_continuation() -> None:
    """BF-03 §16/§17: the session budget and the cooldown guard *new*
    automatic openings. The bundle does not carry them at all, and the
    frozen reference never reads them on this path — the pin is that the
    profile's own fact set has no field for them."""

    field_names = {
        field.name for field in dataclasses.fields(AutoContinuationFacts)
    }
    assert "automatic_session_budget_exhausted" not in field_names
    assert "hard_cooldown_active" not in field_names


def test_the_flow_protection_still_stops_an_automatic_continuation() -> None:
    verdict = decide_auto_continuation(
        _continuation_facts(hard_protected_flow=True)
    )
    assert verdict.primary_reason == "HARD_PROTECTED_FLOW"


def test_the_auto_teach_setting_stops_only_an_auto_opened_moment() -> None:
    """BF-03 §17: a user-authorized episode is not the setting's to stop."""

    auto_opened = decide_auto_continuation(
        _continuation_facts(
            automatic_teaching_enabled=False, moment_consent_class="AUTO_OPENED"
        )
    )
    assert auto_opened.primary_reason == "AUTO_TEACH_DISABLED"
    user_authorized = decide_auto_continuation(
        _continuation_facts(
            automatic_teaching_enabled=False,
            moment_consent_class="USER_AUTHORIZED",
        )
    )
    assert user_authorized.decision == "ALLOW"


def test_the_hard_caps_fire_on_the_move_class() -> None:
    retry_blocked = decide_auto_continuation(
        _continuation_facts(
            hard_attempt_limit_exhausted=True, proposed_action="RETRY"
        )
    )
    assert retry_blocked.primary_reason == "HARD_ATTEMPT_LIMIT"
    reveal_exempt = decide_auto_continuation(
        _continuation_facts(
            hard_attempt_limit_exhausted=True, proposed_action="REVEAL"
        )
    )
    assert reveal_exempt.decision == "ALLOW"
    turn_cap = decide_auto_continuation(
        _continuation_facts(
            hard_teaching_turn_limit_exhausted=True, proposed_action="HINT"
        )
    )
    assert turn_cap.primary_reason == "HARD_TEACHING_TURN_LIMIT"
    terminalizing = decide_auto_continuation(
        _continuation_facts(
            hard_teaching_turn_limit_exhausted=True,
            proposed_action="EXPLANATION",
            terminalizing_action=True,
        )
    )
    assert terminalizing.decision == "ALLOW"


def test_auto_continuation_never_reports_the_snapshot_fact() -> None:
    """BF-03 v1.1's cross-layer repair: an active moment's own new Evidence
    does not invalidate its continuation, and the fact is not part of this
    profile's completeness set (the reference's ``_critical_unknown`` checks
    six facts plus the gate state)."""

    verdict = decide_auto_continuation(
        _continuation_facts(learning_snapshot_status="UNKNOWN")
    )
    assert verdict.decision == "ALLOW"
    assert verdict.missing_or_unknown == ()
    for key in AUTO_CONTINUATION_FACT_KEYS:
        assert key != "LEARNING_SNAPSHOT"


# ---------------------------------------------------------------------------
# the consent-class derivation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("AUTOMATIC", "AUTO_OPENED"),
        ("USER_INITIATED", "USER_AUTHORIZED"),
        ("MANUAL_FOCUS", "USER_AUTHORIZED"),
        ("SCHEDULED_STUDY", "USER_AUTHORIZED"),
    ],
)
def test_moment_consent_class_follows_the_source(
    source: str, expected: str
) -> None:
    assert moment_consent_class_of(source) == expected


def test_moment_consent_class_refuses_an_unknown_source() -> None:
    with pytest.raises(GateInputError):
        moment_consent_class_of("RESUMED_FROM_BACKUP")


# ---------------------------------------------------------------------------
# the two USER_INITIATED profiles still exist, unchanged, for the same
# contexts (the automatic branch is additive)
# ---------------------------------------------------------------------------


def test_the_user_profiles_keep_the_intents_they_require() -> None:
    assert USER_INITIATED_CONTINUATION_INTENTS == (
        "ACTIVE_TEACHING_CONTINUATION",
    )
    from elc.teaching.gate import USER_INITIATED_OPEN_INTENTS

    assert USER_INITIATED_OPEN_INTENTS == (
        "LEARNING_REQUEST",
        "TARGETED_LEARNING_REQUEST",
    )
