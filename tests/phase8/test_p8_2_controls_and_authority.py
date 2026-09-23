"""P8-2 ⑤⑥ — the automatic controls, derived; and §13's one field's authority.

Two claims, one cut:

1. **the three automatic-open controls are derived, not hand-passed**
   (:mod:`elc.runtime.automatic_controls` and
   :meth:`elc.runtime.automatic_teaching.TeachingControlFacts.derived`), and
   they are the Gate's *inputs* — driven here through the real automatic unit
   over the real durable world, so the DENY reason each control produces is
   read off the real profile;
2. **``natural_break_available`` has one authority** — docs/DOMAIN_MODEL.md
   §13's ``ConversationPriorityView``, read by the shadow run out of the
   request it was handed (the hand-passed boolean is gone), with the
   fail-closed reading for an absent view and BF-02's frozen 43-case replay
   unchanged by the move.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import os
import sqlite3
import subprocess
import sys
from dataclasses import replace

import pytest

from elc.planner import stress_suite
from elc.planner.controller import PlannerService
from elc.planner.scope import (
    ConversationPriorityView,
    FlowPriority,
    InteractionPhase,
)
from elc.planner.shadow import run_shadow
from elc.platform.db.decision_cycle_store import SqliteDecisionCycleStore
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.db.planner_store import SqlitePlannerRecordStore
from elc.platform.types import (
    DecisionCycleId,
    Ok,
    PlannerExecutionStatusValue,
)
from elc.runtime.automatic_controls import (
    AutomaticControls,
    automatic_controls_of,
)
from elc.runtime.automatic_teaching import (
    AutomaticTeachingTurn,
    TeachingControlFacts,
    automatic_gate_decision_id,
    automatic_moment_id,
    decide_automatic_teaching,
)
from elc.teaching.controller import TeachingController
from elc.teaching.store import SqliteTeachingStore
from elc.teaching.types import (
    MomentSource,
    MomentState,
    PresentationPhase,
    SessionBudgetView,
    TeachingMomentRecord,
    TeachingSupportLevel,
    TeachingTargetRef,
)
from tests.conftest import BASELINES, REPO_ROOT
from tests.phase7.conftest import (
    DAY_TWO,
    TARGET_ID,
    WATERMARK,
    proposal,
    source_text,
)
from tests.phase8.conftest import (
    CONV,
    CycleWorld,
    request_of,
    supply_of,
    table_counts,
)

CONTROLS_MODULE = "src/elc/runtime/automatic_controls.py"
SHADOW_MODULE = "src/elc/planner/shadow.py"
STRESS_SUITE_MODULE = "src/elc/planner/stress_suite.py"
CASES_PATH = BASELINES / "planner" / "planner_stress_cases_v1_1.json"

TEACHING_TABLES = (
    "gate_execution_status",
    "gate_decision",
    "teaching_moment",
    "active_teaching_lock",
    "generation_action_intent",
)


def _budget_view(
    *,
    remaining: int | None = None,
    cooldown: float = 0.0,
) -> SessionBudgetView:
    """One §5.2 value: only the two fields the controls read vary."""

    return SessionBudgetView(
        conversation_id=CONV,
        policy_version=None,
        automatic_teaching_used=0,
        automatic_teaching_remaining=remaining,
        probe_budget_remaining=None,
        cooldown_remaining=cooldown,
        recent_skips=0,
        recent_rejections=0,
        fatigue_signal=None,
        as_of=DAY_TWO,
    )


def _priority_view(
    *, flow: FlowPriority = FlowPriority.NORMAL, natural_break: bool = False
) -> ConversationPriorityView:
    return ConversationPriorityView(
        flow_priority=flow,
        interaction_phase=InteractionPhase.DEEP_EXCHANGE,
        natural_break_available=natural_break,
    )


# -- ⑤ the three controls ----------------------------------------------------


@pytest.mark.parametrize(
    "remaining,expected",
    [
        (None, False),
        (0, True),
        (-1, True),
        (1, False),
        (3, False),
    ],
)
def test_the_budget_control_reads_remaining_and_never_reads_none_as_zero(
    remaining: int | None, expected: bool
) -> None:
    """``None`` is "no vocabulary was read" — not "spent". Reading it as
    exhausted would deny every automatic opening in a world whose policy has
    no budget column; reading it as remaining would spend a budget nobody can
    see."""

    controls = automatic_controls_of(
        session_budget_view=_budget_view(remaining=remaining),
        conversation_priority_view=None,
    )
    assert controls.automatic_session_budget_exhausted is expected


@pytest.mark.parametrize(
    "cooldown,expected", [(0.0, False), (0.1, True), (600.0, True)]
)
def test_the_cooldown_control_reads_the_views_remaining(
    cooldown: float, expected: bool
) -> None:
    controls = automatic_controls_of(
        session_budget_view=_budget_view(cooldown=cooldown),
        conversation_priority_view=None,
    )
    assert controls.hard_cooldown_active is expected


@pytest.mark.parametrize(
    "flow,expected",
    [
        (FlowPriority.PROTECTED, True),
        (FlowPriority.HIGH, False),
        (FlowPriority.NORMAL, False),
        (FlowPriority.LOW, False),
    ],
)
def test_the_flow_control_is_protected_and_only_protected(
    flow: FlowPriority, expected: bool
) -> None:
    """§13's word, compared as P7-2's enum: ``HIGH`` is not ``PROTECTED``.

    BF-03 §12's flow protection fires on the one word; a mapping that treated
    ``HIGH`` as protected would deny openings the frozen reference allows."""

    controls = automatic_controls_of(
        session_budget_view=None,
        conversation_priority_view=_priority_view(flow=flow),
    )
    assert controls.hard_protected_flow is expected


def test_absent_views_answer_false_and_only_false() -> None:
    """The fail-open posture, both directions: with both views absent every
    control is ``False``; with only one absent, only its own controls are."""

    nothing = automatic_controls_of(
        session_budget_view=None, conversation_priority_view=None
    )
    assert nothing == AutomaticControls(
        automatic_session_budget_exhausted=False,
        hard_cooldown_active=False,
        hard_protected_flow=False,
    )
    only_flow = automatic_controls_of(
        session_budget_view=None,
        conversation_priority_view=_priority_view(flow=FlowPriority.PROTECTED),
    )
    assert only_flow.hard_protected_flow is True
    assert only_flow.automatic_session_budget_exhausted is False
    only_budget = automatic_controls_of(
        session_budget_view=_budget_view(remaining=0, cooldown=5.0),
        conversation_priority_view=None,
    )
    assert only_budget.automatic_session_budget_exhausted is True
    assert only_budget.hard_cooldown_active is True
    assert only_budget.hard_protected_flow is False


def test_the_derivation_is_pure_and_total() -> None:
    """Same inputs, same answer; and no input combination raises."""

    first = automatic_controls_of(
        session_budget_view=_budget_view(remaining=0, cooldown=1.0),
        conversation_priority_view=_priority_view(flow=FlowPriority.PROTECTED),
    )
    second = automatic_controls_of(
        session_budget_view=_budget_view(remaining=0, cooldown=1.0),
        conversation_priority_view=_priority_view(flow=FlowPriority.PROTECTED),
    )
    assert first == second
    assert first == AutomaticControls(True, True, True)


def test_the_module_registers_its_authorities_and_the_fail_open_reading() -> None:
    """The mapping's own text names the three authorities (BF-03 §16/§17, §13)
    and the absent-view reading with its revisit — the claim a reviewer checks
    against the Gate's profiles."""

    module_doc = AutomaticControls.__doc__ or ""
    assert "Gate" in module_doc and "§13" in module_doc
    controls_doc = automatic_controls_of.__doc__ or ""
    assert "None" in controls_doc and "fail-open" in controls_doc
    source = source_text(CONTROLS_MODULE)
    for phrase in ("BF-03 §16", "BF-03 §17", "FlowPriority.PROTECTED", "Revisit"):
        assert phrase in source, phrase


def test_the_module_is_sql_free_and_clock_free() -> None:
    """Gate item 2 covers this package; the pin is that this module adds no
    machinery of its own — no SQL, no db import, no clock."""

    source = source_text(CONTROLS_MODULE)
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    assert "sqlite3" not in imported
    assert not [name for name in imported if name.startswith("elc.platform.db")]
    assert "datetime" not in imported
    for marker in ("insert into", "update ", "delete from"):
        assert marker not in source.lower()


def test_the_controls_module_imports_cold() -> None:
    program = "\n".join(
        [
            "import os, sys",
            "ROOT = os.environ['ROOT']",
            "sys.path[:0] = [os.path.join(ROOT, 'src'), ROOT]",
            "from elc.runtime.automatic_controls import automatic_controls_of",
            "from elc.runtime.automatic_teaching import TeachingControlFacts",
            "print('COLD-CONTROLS', automatic_controls_of("
            "session_budget_view=None, conversation_priority_view=None))",
        ]
    )
    process = subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPO_ROOT,
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", ROOT=str(REPO_ROOT)),
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert process.returncode == 0, process.stderr
    assert "AutomaticControls(" in process.stdout


# -- the record's derived constructor ---------------------------------------


def test_derived_sets_the_three_controls_and_keeps_every_other_default() -> None:
    facts = TeachingControlFacts.derived(
        session_budget_view=_budget_view(remaining=0, cooldown=60.0),
        conversation_priority_view=_priority_view(flow=FlowPriority.PROTECTED),
    )
    assert facts.automatic_session_budget_exhausted is True
    assert facts.hard_cooldown_active is True
    assert facts.hard_protected_flow is True
    healthy = TeachingControlFacts()
    for field in dataclasses.fields(TeachingControlFacts):
        if field.name in {
            "automatic_session_budget_exhausted",
            "hard_cooldown_active",
            "hard_protected_flow",
        }:
            continue
        assert getattr(facts, field.name) == getattr(healthy, field.name), (
            field.name
        )


def test_derived_leaves_automatic_teaching_enabled_to_its_own_authority() -> None:
    """The enable switch's authority is the product mode × rollout stage
    (p8-5) and the Planner's assembled value; deriving it here would invent a
    second one."""

    facts = TeachingControlFacts.derived(
        session_budget_view=None, conversation_priority_view=None
    )
    assert facts.automatic_teaching_enabled is True
    source = source_text(
        "src/elc/runtime/automatic_teaching.py"
    )
    assert "automatic_teaching_enabled" in source
    doc = TeachingControlFacts.derived.__doc__ or ""
    assert "automatic_teaching_enabled" in doc
    assert "p8-5" in doc


def test_a_caller_can_override_one_derived_control_explicitly() -> None:
    """The declared record stays the primary shape: an override is
    ``dataclasses.replace``, and it lands verbatim."""

    derived = TeachingControlFacts.derived(
        session_budget_view=_budget_view(remaining=0),
        conversation_priority_view=None,
    )
    assert derived.automatic_session_budget_exhausted is True
    overridden = replace(derived, automatic_session_budget_exhausted=False)
    assert overridden.automatic_session_budget_exhausted is False
    assert overridden.hard_protected_flow is False


# -- the controls as the Gate's inputs, over the durable world ---------------


def _cycle_record(db: sqlite3.Connection, fence: RuntimeEpochFence, cycle):
    read = SqliteDecisionCycleStore(db, fence).get_decision_cycle(
        cycle.decision_cycle_id
    )
    assert isinstance(read, Ok), read
    assert read.value is not None
    return read.value


def _moment_template(turn_id) -> TeachingMomentRecord:
    """The §15 template an ALLOW would open (P8-1's shape, kept minimal)."""

    return TeachingMomentRecord(
        moment_id=automatic_moment_id(turn_id),
        conversation_id=CONV,
        persona_id=None,
        source=MomentSource.AUTOMATIC,
        decision_cycle_id=DecisionCycleId("dc-unused"),
        candidate_id="cand-unused",
        gate_decision_id=automatic_gate_decision_id(turn_id),
        focus_target=TeachingTargetRef("RESOURCE", str(TARGET_ID)),
        supporting_targets=(),
        target_mode="RESOURCE_PRACTICE",
        learning_intent="ESTABLISH",
        evidence_modality="TEXT_PRODUCTION",
        evidence_goal=None,
        preferred_support_ceiling=None,
        learning_snapshot_id=None,
        evidence_watermark=None,
        curriculum_version=None,
        content_version=None,
        policy_version=None,
        lifecycle_state=MomentState.OPENING,
        presentation_phase=PresentationPhase.INITIAL_PROMPT,
        attempt_index=0,
        support_level=TeachingSupportLevel.NONE,
        completion_outcome=None,
        abort_reason=None,
        state_version=1,
    )


def _decide(
    db: sqlite3.Connection,
    fence: RuntimeEpochFence,
    cycle: CycleWorld,
    controls: TeachingControlFacts,
):
    """One automatic decision over the real chain: a SELECT shadow run, the
    real CP2 planner records, the real teaching store."""

    shadow = run_shadow(
        request_of(decision_cycle_id=cycle.decision_cycle_id),
        supply=supply_of(proposal("cand-p8-2")),
        current_learning_watermark=WATERMARK,
    )
    assert shadow.execution_status is PlannerExecutionStatusValue.SUCCEEDED
    assert shadow.decision is not None and shadow.decision.value == "SELECT"
    record = _cycle_record(db, fence, cycle)
    return decide_automatic_teaching(
        turn=AutomaticTeachingTurn(
            turn_id=record.turn_id,
            conversation_id=CONV,
            persona_id=None,
            cycle=record,
            moment=_moment_template(record.turn_id),
            owner_epoch=fence.current,
        ),
        outcome=shadow.outcome,
        controls=controls,
        planner_store=SqlitePlannerRecordStore(db, fence),
        teaching=TeachingController(SqliteTeachingStore(db, fence)),
    )


def test_an_exhausted_budget_denies_the_automatic_opening(
    db: sqlite3.Connection,
    fence: RuntimeEpochFence,
    cycle: CycleWorld,
) -> None:
    """BF-03 §16: ``remaining <= 0`` is the Gate's own reason, and no moment
    is opened — the derived fact is the input the profile already reads."""

    decided = _decide(
        db,
        fence,
        cycle,
        TeachingControlFacts.derived(
            session_budget_view=_budget_view(remaining=0),
            conversation_priority_view=None,
        ),
    )
    assert isinstance(decided, Ok), decided
    result = decided.value
    assert result.gate_verdict is not None
    assert result.gate_verdict.decision == "DENY"
    assert result.gate_verdict.primary_reason == "AUTO_SESSION_BUDGET_EXHAUSTED"
    assert result.moment_id is None
    assert result.normal_persona_generation is True
    assert table_counts(db, "teaching_moment") == {"teaching_moment": 0}


def test_a_running_cooldown_denies_the_automatic_opening(
    db: sqlite3.Connection,
    fence: RuntimeEpochFence,
    cycle: CycleWorld,
) -> None:
    """BF-03 §17, through the derived fact."""

    decided = _decide(
        db,
        fence,
        cycle,
        TeachingControlFacts.derived(
            session_budget_view=_budget_view(cooldown=1.0),
            conversation_priority_view=None,
        ),
    )
    assert isinstance(decided, Ok), decided
    assert decided.value.gate_verdict is not None
    assert decided.value.gate_verdict.primary_reason == "HARD_COOLDOWN_ACTIVE"
    assert decided.value.moment_id is None


def test_a_protected_flow_denies_the_automatic_opening(
    db: sqlite3.Connection,
    fence: RuntimeEpochFence,
    cycle: CycleWorld,
) -> None:
    """§13's one word, through the derived fact."""

    decided = _decide(
        db,
        fence,
        cycle,
        TeachingControlFacts.derived(
            session_budget_view=None,
            conversation_priority_view=_priority_view(
                flow=FlowPriority.PROTECTED
            ),
        ),
    )
    assert isinstance(decided, Ok), decided
    assert decided.value.gate_verdict is not None
    assert decided.value.gate_verdict.primary_reason == "HARD_PROTECTED_FLOW"
    assert decided.value.moment_id is None


def test_an_unreadable_budget_does_not_block_the_automatic_opening(
    db: sqlite3.Connection,
    fence: RuntimeEpochFence,
    cycle: CycleWorld,
) -> None:
    """The fail-open reading, end to end: a policy with no budget vocabulary
    answers ``remaining=None``, and that is **not** an exhausted budget — the
    opening proceeds and its five CP2 facts are durable."""

    decided = _decide(
        db,
        fence,
        cycle,
        TeachingControlFacts.derived(
            session_budget_view=_budget_view(remaining=None, cooldown=0.0),
            conversation_priority_view=_priority_view(
                flow=FlowPriority.NORMAL
            ),
        ),
    )
    assert isinstance(decided, Ok), decided
    result = decided.value
    assert result.gate_verdict is not None
    assert result.gate_verdict.decision == "ALLOW"
    assert result.moment_id is not None
    assert result.normal_persona_generation is False
    assert table_counts(db, "teaching_moment") == {"teaching_moment": 1}
    stored = db.execute(
        "SELECT source FROM teaching_moment WHERE moment_id = ?",
        (str(result.moment_id),),
    ).fetchone()
    assert stored == ("AUTOMATIC",)


# -- ⑥ §13's one field has one authority ------------------------------------


def test_the_shadow_run_takes_no_natural_break_argument() -> None:
    """The hand-passed boolean is gone from both faces, and a caller that
    still passes one is refused rather than silently ignored."""

    for face in (run_shadow, PlannerService.run_shadow):
        assert "natural_break_available" not in inspect.signature(
            face
        ).parameters
    with pytest.raises(TypeError):
        run_shadow(request_of(), natural_break_available=True)


def test_a_view_with_a_natural_break_marks_the_context() -> None:
    """The value the run assembles is the §13 view's own field — read off the
    kernel's trace, where the assembly put it."""

    record = run_shadow(
        request_of(
            conversation_priority_view=_priority_view(natural_break=True)
        ),
        supply=supply_of(proposal("cand-p8-2")),
        current_learning_watermark=WATERMARK,
    )
    assert record.trace.context.natural_break_available is True


def test_a_view_without_a_natural_break_marks_none() -> None:
    record = run_shadow(
        request_of(
            conversation_priority_view=_priority_view(natural_break=False)
        ),
        supply=supply_of(proposal("cand-p8-2")),
        current_learning_watermark=WATERMARK,
    )
    assert record.trace.context.natural_break_available is False


def test_a_request_with_no_view_reads_fail_closed() -> None:
    """No §13 view: ``False`` — "a value, not a missing authority", the
    reading P7-0's default declares (a natural break one cannot see is not one
    the run may claim)."""

    record = run_shadow(
        request_of(conversation_priority_view=None),
        supply=supply_of(proposal("cand-p8-2")),
        current_learning_watermark=WATERMARK,
    )
    assert record.trace.context.natural_break_available is False


def test_the_shadow_module_reads_the_field_from_the_requests_view() -> None:
    """The claim in the module's own text: the value comes from the request's
    §13 view, and the reading names its authority and its revisit."""

    source = source_text(SHADOW_MODULE)
    assert "request.conversation_priority_view" in source
    assert "_natural_break_available_of" in source
    helper_doc = source[source.index("def _natural_break_available_of") :]
    helper_doc = helper_doc[: helper_doc.index("\ndef run_shadow")]
    assert "§13" in helper_doc
    assert "fail-closed" in helper_doc
    assert "Revisit:" in helper_doc
    # The old sentence — "two facts the request does not carry are declared" —
    # is gone, and judgement 1 no longer lists this view among the unread.
    assert "two facts the request does not carry are declared" not in source
    assert "Three further request" in source
    assert "**one fact the request does not carry is declared" in source


def test_the_moved_stamp_is_recorded_beside_the_stamp() -> None:
    """P8-2 moved one of the stamped readings and the stamp moved with it
    (the p8-2 disposal's ruling, ``sh2``): the reason is stated in the
    comment the constant carries, not left to a diff, and it names the
    phase-7 pin that was moved in the same cut (registered in the receipt).

    The claim this test pins did not weaken with the value — the stamp and
    the readings still do not silently differ; only which way they agreed
    changed (``sh1`` pinned the divergence, ``sh2`` records the move)."""

    lines = source_text(SHADOW_MODULE).splitlines()
    constant = 'SHADOW_MODE_MODEL_VERSION = "sh2"'
    index = next(
        position
        for position, line in enumerate(lines)
        if line.startswith(constant)
    )
    block_lines: list[str] = []
    cursor = index - 1
    while cursor >= 0 and lines[cursor].startswith("#"):
        block_lines.append(lines[cursor])
        cursor -= 1
    # Normalized: the comment's own "#:" prefixes and the line wraps are the
    # file's formatting, not the claim's words.
    block = " ".join(
        " ".join(line.removeprefix("#:").split())
        for line in reversed(block_lines)
    )
    assert "P8-2" in block
    assert "moved with it" in block
    assert "sh2" in block
    assert "tests/phase7" in block


# -- the frozen replays the move must not disturb ---------------------------


def test_the_stress_suite_never_calls_the_shadow_run() -> None:
    """The suite assembles BF-02's frozen context itself
    (:func:`~elc.planner.stress_suite.authority_of`), so the
    ``natural_break_available`` it feeds is the case file's own field — which
    is why P8-2's signature change cannot reach it. Pinned both ways: no
    ``run_shadow`` call, and its own reading of the field is present."""

    source = source_text(STRESS_SUITE_MODULE)
    assert "run_shadow" not in source
    assert "natural_break_available" in source
    assert "authority_of" in source


def test_the_frozen_43_case_replay_is_unchanged() -> None:
    """The regression the signature change could have caused, read off the
    frozen file: the same 43 cases, every one's own ``expected`` holding
    (this suite re-runs the replay; the phase-7 pins are untouched)."""

    cases = stress_suite.load_cases(CASES_PATH)
    assert len(cases) == 43
    verdicts = stress_suite.stress_table(cases)
    assert [verdict.case_id for verdict in verdicts] == [
        str(case["id"]) for case in cases
    ]
    assert all(verdict.passed for verdict in verdicts), [
        verdict.line() for verdict in verdicts if not verdict.passed
    ]
    assert stress_suite.stress_report(cases).rstrip().endswith(
        "BF-02 stress: 43/43 PASS"
    )
