"""P7-4 ① — shadow mode: the Planner runs, and nothing is dispatched.

Three claims are pinned here, and each is pinned by the strongest evidence this
repository can give it:

- **the record is §8's.** docs/IMPLEMENTATION_PLAN.md §8's block ("Planner
  decides / but UI does not auto-teach"; "what would have been selected / why")
  is quoted in the module, and the four recorded fields are the run's **own**
  answers rather than a second opinion — the selected candidate of its decision,
  its reason trace, its execution status and the RuntimeDecisionOutcome that
  status implies (docs/DOMAIN_MODEL.md line 559; RUNTIME_ARCHITECTURE §4 step
  9A);
- **nothing is dispatched.** Structurally (the module's import set is one
  declared set and names no teaching, Gate, runtime, SQL or clock face), by
  module provenance (a real run adds no new module from the dispatch side) and
  behaviourally (a run over a real app.db leaves every table's row count and the
  connection's change counter where it found them);
- **a degraded run reports a status, not a decision.** A request that assembles
  nothing answers DEGRADED with no PlannerDecision — never a synthetic
  NO_TARGET (docs/DOMAIN_MODEL.md §10.1's last sentence, BF-02 §5).

Two faces beside the shadow run stay unwired on purpose and are pinned as
honest refusals rather than as "not tested yet": the dispatch entry
:meth:`PlannerService.plan` and the durable trace read
:meth:`PlannerService.get_planner_evaluation`.
"""

from __future__ import annotations

import ast
import copy
import os
import re
import sqlite3
import subprocess
import sys

import pytest

from elc.planner.candidates import CandidateSupply
from elc.planner.controller import PlannerService
from elc.planner.scope import ScopeResolution
from elc.planner.shadow import (
    SHADOW_MODE_MODEL_VERSION,
    ShadowRun,
    run_shadow,
)
from elc.planner.types import PlanningRequest, UserIntentScope
from elc.platform.types import (
    DecisionCycleId,
    Ok,
    PlannerDecisionOutcome,
    PlannerEvaluationId,
    PlannerExecutionStatusValue,
    RuntimeDecisionOutcomeValue,
)
from elc.scheduler.controller import SchedulerController
from elc.scheduler.types import ReviewState
from elc.user_config.controller import UserConfigController
from elc.user_config.store import SqliteUserConfigStore
from tests.conftest import REPO_ROOT

from .conftest import (
    CONV,
    DAY_ONE,
    DAY_THREE,
    DAY_TWO,
    USER,
    WATERMARK,
    constraint,
    document_text,
    kernel_row,
    learning_snapshot,
    portfolio,
    proposal,
    schedule_item,
    schedule_view,
    source_text,
    teaching_policy,
)

#: The module under test, so a reader can see which claims are structural.
SHADOW_MODULE = "src/elc/planner/shadow.py"
CONTROLLER_MODULE = "src/elc/planner/controller.py"

#: One numbered judgement entry ("7. **…**", ten and up included).
_NUMBERED = re.compile(r"^\d+\. ")

#: Shadow mode's own import set — declared, and asserted by equality: a later
#: cut that needs one more face has to say so here rather than widen it quietly.
#: **P8-4 added ``elc.planner.scope``**, and it is the pure reading face: the
#: run's one §13 field is now read through
#: ``elc.planner.scope.natural_break_available_of`` so the shadow run and the
#: ordinary turn's automatic leg share one answer (the local protocol that used
#: to keep the module out stays; it narrows the *read*, not the import). No
#: dispatch face was added — the set below still holds none of
#: ``DISPATCH_PREFIXES``.
SHADOW_IMPORTS = {
    "__future__",
    "dataclasses",
    "elc.planner.candidates",
    "elc.planner.feature_assembly",
    "elc.planner.kernel",
    "elc.planner.scope",
    "elc.planner.types",
    "elc.platform.types",
    "typing",
}

#: The module prefixes a shadow run may not pull in *while it runs*. The
#: package's own import closure already reaches ``elc.runtime`` (P7-2's
#: ``elc.user_config.constraints`` leg does, before this cut), so the pin is
#: about the run and not about the import — the run is the thing that would
#: dispatch if anything did.
DISPATCH_PREFIXES = (
    "elc.teaching",
    "elc.runtime",
    "elc.platform.db",
    "sqlite3",
)


# -- the world ---------------------------------------------------------------


def supply_of(
    *proposals: object, readiness: str = "R3_TEACHING_READY"
) -> CandidateSupply:
    """P7-2's own answer for a cycle: proposals, their targets' §8.1 levels,
    and the §12 resolution. Built here rather than generated, because BF-02
    §20's inputs are synthetic by contract (the P7-1 suite's own reading)."""

    built = tuple(proposals)
    targets = {getattr(item, "focus_target") for item in built}
    return CandidateSupply(
        proposals=built,  # type: ignore[arg-type]
        gaps=(),
        refusals=(),
        readiness={target: readiness for target in sorted(targets)},
        scope=ScopeResolution(
            scope=UserIntentScope.OPEN,
            request_targets=(),
            reasons=(),
            constraint_view_present=True,
        ),
    )


def request_of(**overrides: object) -> PlanningRequest:
    """One view-complete PlanningRequest; a keyword replaces one leg."""

    bag: dict[str, object] = {
        "decision_cycle_id": DecisionCycleId("dc-p7-4"),
        "learning_snapshot": learning_snapshot(),
        "curriculum_candidate_view": None,
        "schedule_view": schedule_view(kernel_row()),
        "goal_view": portfolio(assessment_targets=()),
        "teaching_policy_view": teaching_policy(),
        "context_opportunity_set": None,
        "planner_constraint_view": constraint(),
        "session_budget_view": None,
        "user_intent_scope": UserIntentScope.OPEN,
        "conversation_priority_view": None,
        "planning_ledger": None,
    }
    bag.update(overrides)
    return PlanningRequest(**bag)  # type: ignore[arg-type]


def empty_request() -> PlanningRequest:
    """The request an orchestrator that assembled nothing would hand over."""

    return request_of(
        decision_cycle_id=DecisionCycleId("dc-p7-4-empty"),
        learning_snapshot=None,
        schedule_view=None,
        goal_view=None,
        teaching_policy_view=None,
        planner_constraint_view=None,
    )


# -- ① the canonical quotes and the record ------------------------------------


def _one_line(text: str) -> str:
    """Whitespace-normalized text, so a quoted canonical line compares equal
    whether the module wraps it or not — the quote is verbatim in its words."""

    return " ".join(text.split())


def test_the_module_quotes_section_8_and_the_two_status_sentences() -> None:
    """§8's shadow block verbatim (line for line), plus the two sentences that
    make a degraded run a status rather than a decision."""

    plan_lines = document_text("IMPLEMENTATION_PLAN.md")
    assert plan_lines[376].strip() == "### Shadow mode"
    assert plan_lines[381].strip() == "Planner decides"
    assert plan_lines[382].strip() == "but UI does not auto-teach"
    assert plan_lines[388].strip() == "what would have been selected"
    assert plan_lines[389].strip() == "why"
    source = _one_line(source_text(SHADOW_MODULE))
    for index in (376, 381, 382, 388, 389):
        assert _one_line(plan_lines[index]) in source, plan_lines[index]

    domain_lines = document_text("DOMAIN_MODEL.md")
    assert "不伪装成" in domain_lines[558]
    assert "PlannerExecutionStatus" in domain_lines[558]
    architecture_lines = document_text("RUNTIME_ARCHITECTURE.md")
    assert (
        architecture_lines[98].strip()
        == "9A PlannerExecutionStatus = DEGRADED/FAILED/UNAVAILABLE"
    )
    assert (
        architecture_lines[99].strip()
        == "→ RuntimeDecisionOutcome = DEGRADED_NO_AUTOMATIC_TEACHING"
    )
    assert _one_line(domain_lines[558]) in source
    assert _one_line(architecture_lines[98]) in source
    assert _one_line(architecture_lines[99]) in source


def test_a_shadow_run_records_the_kernels_own_answers() -> None:
    """The four §8 fields *are* the run's answers — no second computation."""

    record = run_shadow(
        request_of(),
        supply=supply_of(proposal("c-p7-4")),
        current_learning_watermark=WATERMARK,
    )
    assert isinstance(record, ShadowRun)
    assert record.execution_status is PlannerExecutionStatusValue.SUCCEEDED
    assert record.decision is PlannerDecisionOutcome.SELECT
    assert record.would_have_selected == "c-p7-4"
    assert record.no_target_reason is None
    assert record.runtime_decision_outcome is RuntimeDecisionOutcomeValue.NORMAL

    decision = record.outcome.decision
    assert decision is not None
    assert record.would_have_selected == str(decision.selected_candidate_id)
    assert record.planner_evaluation_id == (
        record.outcome.evaluation.planner_evaluation_id
    )
    assert record.why == record.outcome.evaluation.reason_trace
    assert any("SELECT c-p7-4" in line for line in record.why)
    assert record.proposal_count == 1
    assert record.canonical_count == 1
    assert record.frontier_candidate_ids == ("c-p7-4",)

    (row,) = record.trace.candidates
    assert row.candidate_id == "c-p7-4"
    assert row.selected
    assert row.activated
    assert row.utility is not None and row.utility > 0.0


def test_a_request_that_assembles_nothing_degrades_instead_of_deciding() -> None:
    """§10/§10.1/BF-02 §5: a status and no decision — and never a NO_TARGET."""

    record = run_shadow(empty_request(), current_learning_watermark=None)
    assert record.execution_status is PlannerExecutionStatusValue.DEGRADED
    assert record.decision is None
    assert record.would_have_selected is None
    assert record.no_target_reason is None
    assert record.outcome.decision is None
    assert record.runtime_decision_outcome is (
        RuntimeDecisionOutcomeValue.DEGRADED_NO_AUTOMATIC_TEACHING
    )
    assert record.proposal_count == 0
    assert record.canonical_count == 0
    assert record.frontier_candidate_ids == ()
    assert any(
        "FEATURE_ASSEMBLY_INCOMPLETE" in line for line in record.why
    ), record.why
    # P7-4's judgement 7: P7-0's assembly is total, so "no authority at all" is
    # a DEGRADED assembly rather than the kernel's UNAVAILABLE (which belongs to
    # a caller who holds no context object).
    assert record.execution_status is not PlannerExecutionStatusValue.UNAVAILABLE


def test_a_no_target_run_records_the_decision_and_its_reason() -> None:
    """NO_TARGET is a *decision*, not a degradation — the other half of the
    same coupling, and the reason the record carries both fields."""

    row = kernel_row(urgency=0.75)
    record = run_shadow(
        request_of(
            schedule_view=schedule_view(row),
            user_intent_scope=UserIntentScope.JUST_CHAT,
        ),
        supply=supply_of(proposal("c-p7-4")),
        current_learning_watermark=WATERMARK,
    )
    assert record.execution_status is PlannerExecutionStatusValue.SUCCEEDED
    assert record.decision is PlannerDecisionOutcome.NO_TARGET
    assert record.would_have_selected is None
    assert record.no_target_reason == "NO_ELIGIBLE_CANDIDATE"
    assert record.runtime_decision_outcome is RuntimeDecisionOutcomeValue.NORMAL


# -- ② zero dispatch ----------------------------------------------------------


def test_the_shadow_module_imports_no_dispatch_face() -> None:
    """The structural half of the boundary: one declared import set, and no
    teaching / Gate / runtime / SQL / clock face in it or in the module's own
    text."""

    source = source_text(SHADOW_MODULE)
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert imported == SHADOW_IMPORTS
    # Names the *code* uses, docstrings excluded: prose may say what the module
    # refuses to do ("builds no TeachingMoment"), code may not do it.
    named = {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    } | {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    assert named.isdisjoint(
        {
            "TeachingMoment",
            "Gate",
            "start_moment",
            "open_moment",
            "commit",
            "execute",
            "rollback",
            "connect",
            "now",
        }
    ), sorted(named)


def test_a_real_shadow_run_pulls_in_no_dispatch_module() -> None:
    """The provenance half: a cold interpreter imports the module, runs a full
    SELECT shadow, and the run adds **no** module from the dispatch side."""

    program = "\n".join(
        [
                "import os, sys",
                "ROOT = os.environ['ROOT']",
                "sys.path[:0] = [os.path.join(ROOT, 'src'), ROOT]",
            "from tests.phase7.conftest import (",
            "    WATERMARK, constraint, kernel_row, learning_snapshot,",
            "    portfolio, proposal, schedule_view, teaching_policy,",
            ")",
            "from elc.planner.candidates import CandidateSupply",
            "from elc.planner.scope import ScopeResolution",
            "from elc.planner.shadow import run_shadow",
            "from elc.planner.types import PlanningRequest, UserIntentScope",
            "from elc.platform.types import DecisionCycleId",
            "supply = CandidateSupply(",
            "    proposals=(proposal('c-cold'),),",
            "    gaps=(), refusals=(),",
            "    readiness={'res-hedge-i-think': 'R3_TEACHING_READY'},",
            "    scope=ScopeResolution(",
            "        scope=UserIntentScope.OPEN, request_targets=(),",
            "        reasons=(), constraint_view_present=True),",
            ")",
            "request = PlanningRequest(",
            "    decision_cycle_id=DecisionCycleId('dc-cold'),",
            "    learning_snapshot=learning_snapshot(),",
            "    curriculum_candidate_view=None,",
            "    schedule_view=schedule_view(kernel_row()),",
            "    goal_view=portfolio(assessment_targets=()),",
            "    teaching_policy_view=teaching_policy(),",
            "    context_opportunity_set=None,",
            "    planner_constraint_view=constraint(),",
            "    session_budget_view=None,",
            "    user_intent_scope=UserIntentScope.OPEN,",
            "    conversation_priority_view=None,",
            "    planning_ledger=None,",
            ")",
            "before = set(sys.modules)",
            "record = run_shadow(",
            "    request, supply=supply,",
            "    current_learning_watermark=WATERMARK)",
            "added = sorted(set(sys.modules) - before)",
            "offenders = [",
            "    name for name in added",
            f"    if name.startswith({DISPATCH_PREFIXES!r})",
            "]",
            "assert not offenders, offenders",
            "assert record.would_have_selected == 'c-cold', record.would_have_selected",
            "assert record.execution_status.value == 'SUCCEEDED'",
            "assert record.runtime_decision_outcome.value == 'NORMAL'",
            "print('COLD-SHADOW', record.would_have_selected, len(added))",
        ]
    )
    env = dict(
        os.environ,
        PYTHONDONTWRITEBYTECODE="1",
        ROOT=str(REPO_ROOT),
    )
    proc = subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, proc.stderr
    assert "COLD-SHADOW c-cold" in proc.stdout
    # The constant's *content* is the pin, not only its use: emptied or
    # widened, the offender scan above would stay silent, so the four prefixes
    # a shadow run may not pull in are asserted here as the list itself.
    assert DISPATCH_PREFIXES == (
        "elc.teaching",
        "elc.runtime",
        "elc.platform.db",
        "sqlite3",
    )


def _table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    names = [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        )
    ]
    return {
        name: conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
        for name in names
    }


def test_a_shadow_run_leaves_the_durable_world_untouched(
    db: sqlite3.Connection,
    user_config_store: SqliteUserConfigStore,
    user_config_controller: UserConfigController,
    learning_controller,
    scheduler_store,
) -> None:
    """The behavioural half: real §5.1/§5.2/§9 rows, read back through the real
    faces, a shadow run that selects — and not one row, count or change."""

    assert isinstance(
        user_config_store.upsert_teaching_policy(teaching_policy()), Ok
    )
    assert isinstance(
        user_config_store.upsert_goal_portfolio(
            portfolio(assessment_targets=())
        ),
        Ok,
    )
    assert isinstance(
        user_config_store.record_planner_constraint(constraint()), Ok
    )
    watermark = learning_controller.get_learning_watermark()
    assert isinstance(watermark, Ok)
    row = schedule_item(
        "si-p7-4",
        review_state=ReviewState.DUE,
        urgency=0.75,
        window_start=DAY_ONE,
        window_end=DAY_THREE,
        watermark=str(watermark.value),
        version="sv-p7-4",
    )
    assert isinstance(scheduler_store.upsert_schedule_item(row), Ok)

    policy = user_config_controller.get_teaching_policy(USER)
    goals = user_config_controller.get_goal_portfolio(USER)
    constraints = user_config_controller.get_planner_constraint_view(DAY_TWO, CONV)
    view = SchedulerController(
        scheduler_store, learning=learning_controller
    ).get_schedule_view(DAY_TWO)
    for result in (policy, goals, constraints, view):
        assert isinstance(result, Ok)
    assert view.value.due_items, "the world has no due row — nothing asserted"

    request = request_of(
        learning_snapshot=learning_snapshot(watermark.value),
        schedule_view=view.value,
        teaching_policy_view=policy.value,
        goal_view=goals.value,
        planner_constraint_view=constraints.value,
    )
    before_counts = _table_counts(db)
    before_changes = db.total_changes
    assert before_counts, "the schema is empty — nothing asserted"

    record = run_shadow(
        request,
        supply=supply_of(
            proposal(
                "c-p7-4-real",
                schedule_urgency=row.review_urgency,
                schedule_row=row,
            )
        ),
        current_learning_watermark=watermark.value,
    )

    assert record.would_have_selected == "c-p7-4-real"
    assert record.execution_status is PlannerExecutionStatusValue.SUCCEEDED
    assert db.total_changes == before_changes
    assert _table_counts(db) == before_counts


def test_two_runs_agree_and_leave_no_module_level_state() -> None:
    """Purity in the form that also catches a side effect that never reaches a
    store: two runs are equal, and every module-level container is where the
    first run found it."""

    import elc.planner.shadow as shadow_module

    def containers() -> dict[str, object]:
        return {
            name: copy.deepcopy(value)
            for name, value in vars(shadow_module).items()
            if not name.startswith("__")
            and isinstance(value, (list, dict, set))
        }

    supply = supply_of(proposal("c-p7-4"))
    request = request_of()
    before = containers()
    first = run_shadow(
        request, supply=supply, current_learning_watermark=WATERMARK
    )
    second = run_shadow(
        request, supply=supply, current_learning_watermark=WATERMARK
    )
    assert first == second
    assert first.would_have_selected == "c-p7-4"
    assert containers() == before
    # Moved by the p8-2 disposal (was "sh1"): P8-2 moved one of the stamped
    # readings (``natural_break_available`` left this module's declaration for
    # §13's view), and the constant's own rule is that it moves with them.
    assert SHADOW_MODE_MODEL_VERSION == "sh2"


# -- ③ the two faces beside it ------------------------------------------------


def test_the_service_forwards_the_shadow_run_and_refuses_the_unwired_faces() -> None:
    """Forwarding is the controller's whole job here; the dispatch entry and
    the durable trace read refuse with their reason, not with an invented
    record.

    P8-0 changed the trace read's *reason*, not its refusal: the §14 store
    now exists (migration 0015's ``planner_evaluation`` table, read through
    ``elc.platform.db.planner_store``), so the pin below holds the message to
    the new carrier — the table the read would go through — instead of the
    retired ``NO_TABLE_V1`` sentence."""

    request = request_of()
    supply = supply_of(proposal("c-p7-4"))
    service = PlannerService()
    assert service.run_shadow(
        request, supply=supply, current_learning_watermark=WATERMARK
    ) == run_shadow(
        request, supply=supply, current_learning_watermark=WATERMARK
    )

    with pytest.raises(NotImplementedError) as dispatch:
        service.plan(request)
    assert "shadow mode" in str(dispatch.value)

    with pytest.raises(NotImplementedError) as trace_read:
        service.get_planner_evaluation(PlannerEvaluationId("pe-p7-4"))
    assert "planner_evaluation" in str(trace_read.value)
    assert "store" in str(trace_read.value)


def test_the_service_module_quotes_its_two_refusals() -> None:
    """The controller says which faces are unwired and why — the scope claim
    its docstring makes, read off the module rather than trusted. Since P8-0
    the durable trace read's sentence names the store it would read
    (``planner_evaluation``), not the retired ``NO_TABLE_V1`` claim."""

    source = source_text(CONTROLLER_MODULE)
    assert "shadow mode" in source
    assert "NotImplementedError" in source
    assert "planner_evaluation" in source
    assert "run_shadow" in source


def test_the_shadow_modules_readings_each_carry_a_revisit() -> None:
    """The module's own claim ("each entry … names the condition that re-opens
    it"), read one entry at a time, with the floor this cut declares."""

    source = source_text(SHADOW_MODULE)
    start = source.index("**Declared judgements.**")
    end = source.index("**Versioning.**")
    entries: list[str] = []
    current: list[str] = []
    for line in source[start:end].splitlines():
        if _NUMBERED.match(line.strip()):
            if current:
                entries.append("\n".join(current))
            current = [line]
        elif current:
            current.append(line)
    if current:
        entries.append("\n".join(current))
    assert len(entries) >= 7, len(entries)
    for entry in entries:
        assert "Revisit:" in entry, entry[:120]
