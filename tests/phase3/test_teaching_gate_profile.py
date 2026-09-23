"""VAL ③ — the Teaching Gate's USER_INITIATED OPEN applicable profile.

The repo-native profile (src/elc/teaching/gate.py) is checked three ways:

1. vocabulary pins — the deny precedence and the critical fact keys are the
   frozen BF-03 v1.1 words;
2. behaviour — every applicable check family fires its exact reason code,
   the precedence ordering is deterministic, and critical-state unknown
   always yields DEGRADED with no GateDecision (never a synthetic DENY);
3. a differential matrix against the frozen reference
   (behavioral_baselines/gate/teaching_gate_reference_v1_1.py, loaded as a
   test oracle only — nothing under behavioral_baselines is imported by
   src/ and nothing there is modified).

The one deliberate divergence is pinned explicitly: an AUTOMATIC OPEN needs
Planner SUCCEEDED + SELECT, a USER_INITIATED OPEN does not (the frozen
reference predates that specialization and raises a contract error without
the planner fields; the repo-native profile takes the explicit request
candidate plus its DecisionCycle and fabricates no PlannerDecision).
"""

from __future__ import annotations

import dataclasses
import hashlib
import importlib.util
import inspect
import json
import sys
from dataclasses import replace
from typing import Any

import pytest

from elc.teaching import gate as gate_module
from elc.teaching.gate import (
    DENY_PRECEDENCE,
    GATE_POLICY_VERSION,
    MISSING_OR_UNKNOWN_FACT_KEYS,
    SAFETY_PRIVACY_NO_SOURCE,
    TARGET_SUPPRESSED_NO_SOURCE,
    USER_INITIATED_OPEN_REASON_CODES,
    AutomaticOpenFacts,
    GateInputError,
    UserInitiatedOpenFacts,
    decide_automatic_open,
    decide_user_initiated_open,
)
from tests.conftest import BASELINES, DOCS_ROOT

GATE_REFERENCE = (
    BASELINES / "gate" / "teaching_gate_reference_v1_1.py"
)
MANIFEST = DOCS_ROOT / "manifest.json"


def _reference() -> Any:
    spec = importlib.util.spec_from_file_location(
        "p3_1a_gate_reference_v1_1", GATE_REFERENCE
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.dont_write_bytecode = True  # keep the baseline tree byte-identical
    spec.loader.exec_module(module)
    return module


def _base_facts() -> UserInitiatedOpenFacts:
    return UserInitiatedOpenFacts(
        decision_cycle_id="dcy-turn-1",
        candidate_id="cand-explicit-turn-1",
    )


def _reference_request(facts: UserInitiatedOpenFacts) -> dict[str, Any]:
    """The facts as the frozen reference's dict.

    The planner fields are synthesized: the reference validates any OPEN
    against Planner SUCCEEDED + SELECT, so only the execution-admissibility
    core (the part the two implementations share) is compared.
    """

    return {
        "gate_context": facts.gate_context,
        "proposed_action": facts.proposed_action,
        "user_intent_scope": facts.user_intent_scope,
        "authorization_path": facts.authorization_path,
        "authorization_basis": facts.authorization_basis,
        "planner_execution_status": "SUCCEEDED",
        "planner_decision": "SELECT",
        "selected_candidate_id": facts.candidate_id,
        "user_initiated": True,
        "authorization_status": facts.authorization_status,
        "subject_status": facts.subject_status,
        "target_status": facts.target_status,
        "content_status": facts.content_status,
        "safety_privacy_status": facts.safety_privacy_status,
        "lock_state": facts.lock_state,
        "target_suppressed": facts.target_suppressed,
        "gate_state_status": facts.gate_state_status,
    }


# ---------------------------------------------------------------------------
# 1. vocabulary pins
# ---------------------------------------------------------------------------


def test_deny_precedence_is_the_frozen_bf03_v1_1_list() -> None:
    assert tuple(_reference().DENY_PRECEDENCE) == DENY_PRECEDENCE


def test_applicable_reason_codes_are_the_open_subset() -> None:
    assert USER_INITIATED_OPEN_REASON_CODES == (
        "SAFETY_PRIVACY_BLOCK",
        "ACTION_CANCELLED",
        "ACTION_SUPERSEDED",
        "AUTHORIZATION_INVALID",
        "TARGET_INVALID",
        "CONTENT_INVALID",
        "TARGET_SUPPRESSED",
        "USER_INTENT_BLOCK",
        "TEACHING_LOCK_CONFLICT",
    )
    # Continuation-only and automatic-only codes exist in the vocabulary
    # but can never be emitted by this profile.
    for code in (
        "TEACHING_LOCK_INVALID",
        "MOMENT_NOT_CONTINUABLE",
        "AUTO_TEACH_DISABLED",
        "HARD_PROTECTED_FLOW",
        "AUTO_SESSION_BUDGET_EXHAUSTED",
        "HARD_COOLDOWN_ACTIVE",
        "HARD_ATTEMPT_LIMIT",
        "HARD_TEACHING_TURN_LIMIT",
    ):
        assert code not in USER_INITIATED_OPEN_REASON_CODES
        assert code in DENY_PRECEDENCE  # still frozen vocabulary


def test_missing_or_unknown_fact_keys_are_the_eight_words() -> None:
    assert MISSING_OR_UNKNOWN_FACT_KEYS == (
        "LEARNING_SNAPSHOT",
        "AUTHORIZATION_STATUS",
        "TARGET_VALIDITY",
        "CONTENT_VALIDITY",
        "LOCK_STATE",
        "SAFETY_PRIVACY_STATUS",
        "SUBJECT_STATUS",
        "GATE_STATE",
    )


def _object_lines_with(source: str, token: str) -> list[str]:
    """The non-comment, non-docstring lines of one object's source that
    carry ``token`` (P8-1's narrowing of the whole-module scan below).

    Same lexical convention the original module-level scan used (a line
    whose stripped form starts with ``#`` or a quote is prose), applied to
    the source of **one object** instead of the whole file — so the pin
    follows the *object* it is about rather than every neighbouring object.
    """

    return [
        line
        for line in source.splitlines()
        if line.strip()
        and not line.strip().startswith(("#", '"', "'"))
        and token in line
    ]


def test_no_planner_decision_is_conceived() -> None:
    """The user-initiated profile never fabricates a PlannerDecision
    (mother decision core ruling ①), and the automatic profile **takes**
    the planner's answer as an input instead.

    **Why this pin was narrowed (P8-1).** The original version scanned the
    whole module's code text for the planner-decision word. That was
    equivalent while the module held only the two user-initiated profiles;
    P8-1 added the AUTOMATIC branch, whose bundle must *carry* the planner
    facts it consumes (a PlannerDecision is an input there, not an
    invention) — so a whole-module scan would now fail for the opposite of
    the property it protects. The pin is narrowed to the two user-initiated
    objects (``inspect.getsource``, so a renamed object fails loudly) and
    **strengthened** by adding the automatic half as an explicit assertion:
    the automatic bundle has the planner fact fields, and its decider
    refuses a run that did not select instead of minting a SELECT.
    """

    field_names = {field.name for field in dataclasses.fields(
        UserInitiatedOpenFacts
    )}
    assert not [name for name in field_names if "planner" in name]
    source = (DOCS_ROOT.parent / "src" / "elc" / "teaching" / "gate.py").read_text(
        encoding="utf-8"
    )
    # The module never reaches for the planner package (unchanged).
    assert "elc.planner" not in source
    # The user-initiated profile and its decider still construct, assert
    # and speak no planner decision — docstrings may *name* the forbidden
    # object while explaining that it is not fabricated, which is why this
    # is the same lexical scan as before, now per object.
    for user_initiated_object in (
        UserInitiatedOpenFacts,
        decide_user_initiated_open,
    ):
        offenders = _object_lines_with(
            inspect.getsource(user_initiated_object), "planner_decision"
        )
        assert not offenders, (user_initiated_object.__name__, offenders)

    # The automatic profile consumes the planner facts as its inputs …
    automatic_fields = {
        field.name for field in dataclasses.fields(AutomaticOpenFacts)
    }
    assert {"planner_execution_status", "planner_decision"} <= automatic_fields
    # The §14 decision column's own name for the selection is readable off
    # the bundle (a read-only alias of candidate_id).
    assert AutomaticOpenFacts(
        decision_cycle_id="dcy-alias", candidate_id="cand-alias"
    ).selected_candidate_id == "cand-alias"
    decision_source = inspect.getsource(decide_automatic_open)
    assert any(
        line.strip().startswith("facts.planner_decision")
        for line in _object_lines_with(
            inspect.getsource(gate_module._check_planner_authorized_open),
            "planner_decision",
        )
    )
    # … reached from the automatic validator (so the check is not dead code).
    assert "_check_planner_authorized_open" in inspect.getsource(
        gate_module._validate_automatic_open
    )
    # The decision word is read off the required facts object; it is never
    # a literal this profile carries around.
    assert "SELECT" not in decision_source, decision_source[:200]
    # … and it never becomes the planner: a run that did not select is a
    # contract error, not a decision this profile invents.
    with pytest.raises(GateInputError):
        decide_automatic_open(
            AutomaticOpenFacts(
                decision_cycle_id="dcy-no-select",
                candidate_id="cand-kept",
                planner_decision="NO_TARGET",
            )
        )


def test_every_planner_decision_line_lives_in_a_declared_automatic_face() -> None:
    """The complement of the narrowing above, closed (P8-1 review F7).

    The narrowed pin scans two user-initiated objects; the whole-module
    invariant it replaced is no longer true, and the review showed the gap
    that left: a *new* module-level object carrying the planner-decision
    word stays green. This pin scans the whole module the same lexical way
    and requires every hit to fall inside one of the three declared
    automatic homes — the bundle's field, the Protocol that names it, and
    the check that reads it. ``inspect`` line ranges (not name matching) are
    what make a moved or renamed object fail loudly.
    """

    allowed = (
        AutomaticOpenFacts,
        gate_module._PlannerAuthorizedOpeningFacts,
        gate_module._check_planner_authorized_open,
    )
    windows: list[range] = []
    for obj in allowed:
        source_lines, start = inspect.getsourcelines(obj)
        windows.append(range(start, start + len(source_lines)))
    module_source = (
        DOCS_ROOT.parent / "src" / "elc" / "teaching" / "gate.py"
    ).read_text(encoding="utf-8")
    offenders = [
        (number, line)
        for number, line in enumerate(module_source.splitlines(), start=1)
        if _object_lines_with(line, "planner_decision")
        and not any(number in window for window in windows)
    ]
    assert not offenders, offenders
    # … and the allow-list is not vacuous: each home really carries the word.
    for obj in allowed:
        assert _object_lines_with(
            inspect.getsource(obj), "planner_decision"
        ), obj.__name__


# ---------------------------------------------------------------------------
# 2. behaviour
# ---------------------------------------------------------------------------


def test_clean_facts_allow() -> None:
    verdict = decide_user_initiated_open(_base_facts())
    assert verdict.execution_status == "SUCCEEDED"
    assert verdict.decision == "ALLOW"
    assert verdict.allowed
    assert verdict.reasons == ()
    assert verdict.primary_reason is None
    assert verdict.missing_or_unknown == ()
    assert verdict.policy_version == GATE_POLICY_VERSION


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"safety_privacy_status": "BLOCK"}, "SAFETY_PRIVACY_BLOCK"),
        ({"target_suppressed": True}, "TARGET_SUPPRESSED"),
        ({"target_status": "INVALID"}, "TARGET_INVALID"),
        ({"target_status": "DEPRECATED"}, "TARGET_INVALID"),
        ({"target_status": "MISSING"}, "TARGET_INVALID"),
        ({"content_status": "INVALID"}, "CONTENT_INVALID"),
        ({"authorization_status": "INVALIDATED"}, "AUTHORIZATION_INVALID"),
        ({"subject_status": "CANCELLED"}, "ACTION_CANCELLED"),
        ({"subject_status": "SUPERSEDED"}, "ACTION_SUPERSEDED"),
        ({"user_intent_scope": "JUST_CHAT"}, "USER_INTENT_BLOCK"),
        ({"user_intent_scope": "NON_LEARNING_TASK"}, "USER_INTENT_BLOCK"),
        ({"lock_state": "OWNED_BY_OTHER"}, "TEACHING_LOCK_CONFLICT"),
        ({"lock_state": "OWNED_BY_THIS_MOMENT"}, "TEACHING_LOCK_CONFLICT"),
    ],
)
def test_each_applicable_check_family_denies_with_its_code(
    overrides: dict[str, Any], expected: str
) -> None:
    facts = replace(_base_facts(), **overrides)
    verdict = decide_user_initiated_open(facts)
    assert verdict.execution_status == "SUCCEEDED"
    assert verdict.decision == "DENY"
    assert verdict.reasons == (expected,)
    assert verdict.primary_reason == expected


def test_multi_blocker_deny_follows_the_frozen_precedence() -> None:
    facts = replace(
        _base_facts(),
        safety_privacy_status="BLOCK",
        target_status="INVALID",
        content_status="INVALID",
        target_suppressed=True,
        lock_state="OWNED_BY_OTHER",
        user_intent_scope="JUST_CHAT",
    )
    verdict = decide_user_initiated_open(facts)
    assert verdict.reasons == (
        "SAFETY_PRIVACY_BLOCK",
        "TARGET_INVALID",
        "CONTENT_INVALID",
        "TARGET_SUPPRESSED",
        "USER_INTENT_BLOCK",
        "TEACHING_LOCK_CONFLICT",
    )
    assert verdict.primary_reason == "SAFETY_PRIVACY_BLOCK"


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
def test_each_critical_unknown_degrades_with_its_fact_key(
    overrides: dict[str, Any], fact_key: str
) -> None:
    facts = replace(_base_facts(), **overrides)
    verdict = decide_user_initiated_open(facts)
    assert verdict.execution_status == "DEGRADED"
    assert verdict.decision is None  # never a synthetic DENY
    assert verdict.reasons == ()
    assert verdict.missing_or_unknown == (fact_key,)


def test_degraded_fact_keys_are_deterministically_sorted() -> None:
    facts = replace(
        _base_facts(),
        learning_snapshot_status="UNKNOWN",
        authorization_status="UNKNOWN",
        target_status="UNKNOWN",
        lock_state="UNKNOWN",
    )
    verdict = decide_user_initiated_open(facts)
    assert verdict.missing_or_unknown == (
        "AUTHORIZATION_STATUS",
        "LEARNING_SNAPSHOT",
        "LOCK_STATE",
        "TARGET_VALIDITY",
    )  # sorted, exactly like the frozen reference


def test_unknown_beats_a_deterministic_blocker() -> None:
    """Critical-state completeness runs first: an unknown fact degrades
    even when another family would deterministically deny — UNKNOWN is
    never laundered into DENY."""

    facts = replace(
        _base_facts(),
        safety_privacy_status="UNKNOWN",
        target_status="INVALID",
    )
    verdict = decide_user_initiated_open(facts)
    assert verdict.execution_status == "DEGRADED"
    assert verdict.decision is None


def test_no_source_environment_facts_are_explicit_and_passing() -> None:
    """The two NO_SOURCE facts: no durable authority exists in P3-1A, so
    they are assembled as explicit ALLOW / not-suppressed — deterministic,
    never UNKNOWN (an absent source must not degrade a user's request)."""

    defaults = _base_facts()
    assert defaults.safety_privacy_status == SAFETY_PRIVACY_NO_SOURCE
    assert defaults.target_suppressed is TARGET_SUPPRESSED_NO_SOURCE
    assert SAFETY_PRIVACY_NO_SOURCE == "ALLOW"
    assert TARGET_SUPPRESSED_NO_SOURCE is False
    assert decide_user_initiated_open(defaults).decision == "ALLOW"


@pytest.mark.parametrize(
    "bad",
    [
        {"gate_context": "AUTO_CONTINUE"},
        {"gate_context": "USER_REQUESTED_CONTINUE"},
        {"proposed_action": "HINT"},
        {"authorization_path": "AUTOMATIC"},
        {"authorization_basis": "ACTIVE_MOMENT"},
        {"decision_cycle_id": ""},
        {"candidate_id": ""},
        {"user_intent_scope": "NOT_A_SCOPE"},
        {"target_status": "BROKEN"},
        {"content_status": "BROKEN"},
        {"lock_state": "BROKEN"},
        {"authorization_status": "BROKEN"},
        {"subject_status": "BROKEN"},
        {"learning_snapshot_status": "BROKEN"},
        {"gate_state_status": "BROKEN"},
        {"safety_privacy_status": "BROKEN"},
    ],
)
def test_contract_errors_raise_instead_of_deciding(bad: dict[str, Any]) -> None:
    """BF-03 §21: a call that violates the interface is a program error —
    not DENY, not DEGRADED (the reference's GateInputError posture)."""

    with pytest.raises(GateInputError):
        decide_user_initiated_open(replace(_base_facts(), **bad))


# ---------------------------------------------------------------------------
# 3. differential matrix against the frozen reference
# ---------------------------------------------------------------------------

_DECISION_MATRIX: tuple[dict[str, Any], ...] = (
    {},
    {"safety_privacy_status": "BLOCK"},
    {"subject_status": "CANCELLED"},
    {"subject_status": "SUPERSEDED"},
    {"authorization_status": "INVALIDATED"},
    {"target_status": "INVALID"},
    {"target_status": "DEPRECATED"},
    {"target_status": "MISSING"},
    {"content_status": "INVALID"},
    {"target_suppressed": True},
    {"user_intent_scope": "LEARNING_REQUEST"},
    {"user_intent_scope": "JUST_CHAT"},
    {"user_intent_scope": "NON_LEARNING_TASK"},
    {"lock_state": "OWNED_BY_OTHER"},
    {"lock_state": "OWNED_BY_THIS_MOMENT"},
    {
        "target_status": "INVALID",
        "content_status": "INVALID",
        "target_suppressed": True,
    },
    {"safety_privacy_status": "BLOCK", "target_status": "INVALID"},
    {
        "safety_privacy_status": "BLOCK",
        "authorization_status": "INVALIDATED",
        "lock_state": "OWNED_BY_OTHER",
        "user_intent_scope": "JUST_CHAT",
    },
)

_FACT_KEY_TO_REFERENCE_FIELD = {
    "LEARNING_SNAPSHOT": "learning_snapshot",  # repo-native; not in BF-03
    "AUTHORIZATION_STATUS": "authorization_status",
    "TARGET_VALIDITY": "target_status",
    "CONTENT_VALIDITY": "content_status",
    "LOCK_STATE": "lock_state",
    "SAFETY_PRIVACY_STATUS": "safety_privacy_status",
    "SUBJECT_STATUS": "subject_status",
    "GATE_STATE": "gate_state",
}

_DEGRADED_MATRIX: tuple[dict[str, Any], ...] = (
    {"authorization_status": "UNKNOWN"},
    {"subject_status": "UNKNOWN"},
    {"target_status": "UNKNOWN"},
    {"content_status": "UNKNOWN"},
    {"safety_privacy_status": "UNKNOWN"},
    {"lock_state": "UNKNOWN"},
    {"authorization_status": "UNKNOWN", "target_status": "UNKNOWN"},
    {"lock_state": "UNKNOWN", "safety_privacy_status": "UNKNOWN"},
)


@pytest.mark.parametrize("overrides", _DECISION_MATRIX)
def test_allow_deny_agrees_with_the_frozen_reference(
    overrides: dict[str, Any],
) -> None:
    gate = _reference()
    facts = replace(_base_facts(), **overrides)
    ours = decide_user_initiated_open(facts)
    theirs = gate.decide(_reference_request(facts))

    assert theirs["execution_status"] == ours.execution_status
    if ours.decision is None:
        assert theirs["decision"] is None
        return
    assert theirs["decision"]["type"] == ours.decision
    if ours.decision == "ALLOW":
        assert theirs["decision"]["reasons"] == []
    else:
        assert theirs["decision"]["reasons"] == list(ours.reasons)
        assert theirs["decision"]["primary_reason"] == ours.primary_reason


@pytest.mark.parametrize("overrides", _DEGRADED_MATRIX)
def test_degraded_agrees_with_the_frozen_reference(
    overrides: dict[str, Any],
) -> None:
    """The §14.1 fact keys map onto the reference's field names (the
    reference has no LEARNING_SNAPSHOT key, so the matrix excludes it);
    the degraded sets and their deterministic order must agree."""

    gate = _reference()
    facts = replace(_base_facts(), **overrides)
    ours = decide_user_initiated_open(facts)
    theirs = gate.decide(_reference_request(facts))

    assert ours.execution_status == "DEGRADED"
    assert theirs["execution_status"] == "DEGRADED"
    assert theirs["decision"] is None
    mapped = sorted(
        _FACT_KEY_TO_REFERENCE_FIELD[key] for key in ours.missing_or_unknown
    )
    assert mapped == theirs["missing_or_unknown"]


def test_user_initiated_open_needs_no_planner_decision() -> None:
    """The pinned divergence: the frozen reference validates every OPEN
    against Planner SUCCEEDED + SELECT (it predates the specialization);
    the repo-native profile decides the explicit-request candidate without
    any planner field and never fabricates a PlannerDecision."""

    gate = _reference()
    facts = _base_facts()
    request = _reference_request(facts)
    request.pop("planner_execution_status")
    request.pop("planner_decision")
    with pytest.raises(gate.GateInputError):
        gate.decide(request)
    assert decide_user_initiated_open(facts).decision == "ALLOW"


# ---------------------------------------------------------------------------
# frozen baseline untouched
# ---------------------------------------------------------------------------


def test_gate_reference_stays_byte_pinned() -> None:
    """behavioral_baselines/ is frozen: the gate reference matches its
    docs/manifest.json pin (sha256 over LF-normalized bytes, the
    cross-platform form the repo uses)."""

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    pinned = manifest["hashes"][
        "behavioral_baselines/gate/teaching_gate_reference_v1_1.py"
    ]
    normalized = GATE_REFERENCE.read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(normalized).hexdigest() == pinned
