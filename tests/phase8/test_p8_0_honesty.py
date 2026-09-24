"""P8-0 ⑦ — layering, one writer, and the faces this cut leaves unwired.

Three kinds of claim, all checkable:

- **the split is structural** — the port (``elc/planner/records.py``) is
  SQL-free and imports nothing from the db/teaching/runtime side, while the
  adapter (``elc/platform/db/planner_store.py``) carries every statement;
- **the writer is one** — no other module in ``src/`` writes the four §14
  tables, the deletion face only deletes them, and the only thing the adapter
  does to ``decision_cycle`` is the back-reference ``UPDATE`` it is allowed;
- **the unwired faces are registered** — the CP2 teaching half (RA §6's
  ``TeachingMoment`` / lease / first action) is not written by this unit, no
  shipped module imports the adapter yet, and the Planner service's durable
  trace read still refuses with its now-true reason.
"""

from __future__ import annotations

import ast
import os
import sqlite3
import subprocess
import sys

import pytest

from elc.planner.controller import PlannerService
from elc.planner.records import PlannerCycleRecords, PlannerRecordStore
from elc.planner.shadow import run_shadow
from elc.platform.db.planner_store import SqlitePlannerRecordStore
from elc.platform.types import (
    PlannerEvaluationId,
    PlannerEvaluationRecord,
    RuntimeDecisionOutcome,
)
from tests.conftest import REPO_ROOT, SRC_ROOT
from tests.phase3.sql_write_scan import write_statements, write_targets
from tests.phase7.conftest import proposal
from tests.phase8.conftest import WATERMARK, request_of, supply_of, table_counts

PORT_MODULE = "src/elc/planner/records.py"
ADAPTER_MODULE = "src/elc/platform/db/planner_store.py"

PLANNER_TABLES = (
    "planner_evaluation",
    "planner_decision",
    "planner_execution_status",
    "runtime_decision_outcome",
)

#: The port's declared import set, asserted by equality: a later cut that
#: needs one more face has to say so here rather than widen it quietly (the
#: ``SHADOW_IMPORTS`` pin's shape). **P9-0 said so**: the port's write face
#: gained the optional ``trace`` keyword (the kernel's own ``PlannerTrace``,
#: which is what the durable ``factor_trace`` document's candidates are built
#: from), so ``elc.planner.kernel`` joins the set. It is the *planner's* own
#: module — still no db/teaching/runtime face and no SQL — which is the claim
#: this pin exists to hold.
PORT_IMPORTS = {
    "__future__",
    "dataclasses",
    "elc.planner.kernel",
    "elc.planner.types",
    "elc.platform.types",
    "typing",
}

#: The four prefixes a module reaching for the dispatch/durable side would
#: pull in (P7-4's list, kept in shape).
DISPATCH_PREFIXES = (
    "elc.teaching",
    "elc.runtime",
    "elc.platform.db",
    "sqlite3",
)


def _imported_modules(relative: str) -> set[str]:
    tree = ast.parse((REPO_ROOT / relative).read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


# -- the split ---------------------------------------------------------------


def test_the_port_module_imports_only_records_and_types() -> None:
    modules = _imported_modules(PORT_MODULE)
    assert modules == PORT_IMPORTS, sorted(modules)
    assert not any(
        module.startswith(prefix) for module in modules
        for prefix in ("sqlite3", "elc.platform.db", "elc.runtime")
    )


def test_the_port_module_carries_no_sql() -> None:
    path = REPO_ROOT / PORT_MODULE
    assert write_targets(path) == set()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            lowered = node.value.lower()
            for marker in ("insert into", "update ", "delete from", "create table"):
                assert marker not in lowered, node.value[:60]


def test_the_adapter_carries_every_statement_and_the_right_verbs() -> None:
    """One writer, and the exact statement classes it may use: INSERT for the
    four §14 tables, UPDATE (and only UPDATE) for the cycle's
    back-reference."""

    statements = write_statements(REPO_ROOT / ADAPTER_MODULE)
    assert statements == {
        "planner_evaluation": ("INSERT",),
        "planner_decision": ("INSERT",),
        "planner_execution_status": ("INSERT",),
        "runtime_decision_outcome": ("INSERT",),
        "decision_cycle": ("UPDATE",),
    }


def test_the_four_tables_have_no_other_writer_in_the_tree() -> None:
    writers: dict[str, set[str]] = {}
    for path in sorted(SRC_ROOT.rglob("*.py")):
        written = write_targets(path) & set(PLANNER_TABLES)
        if written:
            writers[path.relative_to(SRC_ROOT).as_posix()] = written
    assert set(writers) == {
        "deletion/store.py",  # the removal face
        "platform/db/planner_store.py",  # the CP2 unit
    }
    # The deletion face removes, and nothing else: a DELETE-only allowance.
    deletion = write_statements(SRC_ROOT / "deletion" / "store.py")
    for table in PLANNER_TABLES:
        assert deletion.get(table) == ("DELETE",), table


def test_the_adapter_satisfies_the_port(
    db, fence
) -> None:
    """The Protocol is the face a caller depends on, and the adapter *is* it
    (structural typing, checked rather than asserted)."""

    store = SqlitePlannerRecordStore(db, fence)
    assert isinstance(store, PlannerRecordStore)


def test_no_shipped_module_wires_the_adapter_yet() -> None:
    """This cut lands the face; the orchestrator that owns CP2 is a later
    cut's work item, so nothing under ``src/`` calls the adapter."""

    offenders: list[str] = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        if path.relative_to(SRC_ROOT).as_posix() == (
            "platform/db/planner_store.py"
        ):
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            offenders.extend(
                f"{path.name}: {name}"
                for name in names
                if "planner_store" in name
            )
    assert offenders == []


def test_the_planner_package_exports_the_port() -> None:
    """A face a consumer cannot find is a face it re-implements: the port and
    the record one commit returns are package exports."""

    import elc.planner as package

    assert package.PlannerRecordStore is PlannerRecordStore
    assert package.PlannerCycleRecords is PlannerCycleRecords
    for name in ("PlannerRecordStore", "PlannerCycleRecords"):
        assert name in package.__all__, name


# -- the cold start ----------------------------------------------------------


def test_the_new_modules_import_cold_and_pull_in_no_dispatch_face() -> None:
    """A cold interpreter imports the package, then the port: the port adds
    no module from the dispatch/SQL side. The adapter's own cold import is
    checked beside it (it is *supposed* to reach ``elc.platform.db``)."""

    program = "\n".join(
        [
            "import os, sys",
            "ROOT = os.environ['ROOT']",
            "sys.path[:0] = [os.path.join(ROOT, 'src'), ROOT]",
            "import elc.planner",
            "before = set(sys.modules)",
            "import elc.planner.records",
            "added = sorted(set(sys.modules) - before)",
            f"offenders = [n for n in added if n.startswith({DISPATCH_PREFIXES!r})]",
            "assert not offenders, offenders",
            "assert elc.planner.records.PlannerRecordStore is not None",
            "print('COLD-RECORDS', len(added))",
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
    assert "COLD-RECORDS" in proc.stdout

    adapter_program = "\n".join(
        [
            "import os, sys",
            "ROOT = os.environ['ROOT']",
            "sys.path[:0] = [os.path.join(ROOT, 'src'), ROOT]",
            "import elc.platform.db.planner_store as m",
            "assert m.SqlitePlannerRecordStore is not None",
            "print('COLD-ADAPTER')",
        ]
    )
    adapter = subprocess.run(
        [sys.executable, "-c", adapter_program],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert adapter.returncode == 0, adapter.stderr
    assert "COLD-ADAPTER" in adapter.stdout


# -- the record shapes -------------------------------------------------------


def test_the_evaluation_record_carries_the_canonical_columns() -> None:
    from dataclasses import fields

    assert [field.name for field in fields(PlannerEvaluationRecord)] == [
        "planner_evaluation_id",
        "decision_cycle_id",
        "frontier_candidate_ids",
        "ranked_candidate_ids",
        "factor_trace",
        "planner_version",
        "policy_profile_version",
        "created_at",
    ]


def test_the_outcome_record_carries_the_four_non_clock_columns() -> None:
    """§14 lists ``created_at`` on this block too; the record follows the
    sibling-adapter convention (the store stamps it) and the four columns it
    does carry are §14's, in order."""

    from dataclasses import fields

    assert [field.name for field in fields(RuntimeDecisionOutcome)] == [
        "turn_id",
        "decision_cycle_id",
        "outcome",
        "reason_codes",
    ]


# -- the unwired faces -------------------------------------------------------


def test_the_unit_writes_no_teaching_row(
    db, cycle, planner_store
) -> None:
    """RA §6's teaching half — ``TeachingMoment``, the lock lease, the first
    ``GenerationActionIntent`` — belongs to the Gate's automatic face (p8-1).
    This cut's unit writes the Planner half and nothing else."""

    shadow = run_shadow(
        request_of(decision_cycle_id=cycle.decision_cycle_id),
        supply=supply_of(proposal("c-p8-0")),
        current_learning_watermark=WATERMARK,
    )
    assert planner_store.record_planner_cycle(
        turn_id=cycle.turn_id, outcome=shadow.outcome
    )
    assert table_counts(
        db,
        "teaching_moment",
        "active_teaching_lock",
        "generation_action_intent",
        "gate_decision",
    ) == {
        "teaching_moment": 0,
        "active_teaching_lock": 0,
        "generation_action_intent": 0,
        "gate_decision": 0,
    }


def test_the_trace_read_names_the_store_and_still_refuses() -> None:
    """``PlannerService.get_planner_evaluation`` declares a ``PlanningOutcome``
    (object-shaped) and §14's row holds candidate **ids**; the refusal now
    names the store that exists instead of the one that did not."""

    service = PlannerService()
    with pytest.raises(NotImplementedError) as refusal:
        service.get_planner_evaluation(PlannerEvaluationId("pe-p8-0"))
    message = str(refusal.value)
    assert "planner_evaluation" in message
    assert "ranked_candidate_ids" in message
    assert PlannerCycleRecords  # the record the *wired* face would answer


def test_the_ports_readings_each_carry_a_revisit() -> None:
    """The port's own claim ("each names the condition that re-opens it"),
    read one entry at a time, with the floor this cut declares."""

    import re

    source = (REPO_ROOT / PORT_MODULE).read_text(encoding="utf-8")
    start = source.index("**Declared judgements")
    end = source.index('"""', start)
    entries: list[str] = []
    current: list[str] = []
    for line in source[start:end].splitlines():
        if re.match(r"^\d+\. ", line.strip()):
            if current:
                entries.append("\n".join(current))
            current = [line]
        elif current:
            current.append(line)
    if current:
        entries.append("\n".join(current))
    assert len(entries) >= 8, len(entries)
    for entry in entries:
        assert "Revisit:" in entry, entry[:120]


def test_the_tables_the_unit_writes_are_the_ones_the_migration_landed(
    db: sqlite3.Connection,
) -> None:
    """A last cross-check between the two halves of this cut: every table the
    adapter names is a table 0015 created, and every table 0015 created is
    named by the adapter (the statement map above is the other half)."""

    migrated = {
        str(row[0])
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
            " AND name NOT LIKE 'sqlite_%'"
        )
    }
    assert set(PLANNER_TABLES) <= migrated
    statements = write_statements(REPO_ROOT / ADAPTER_MODULE)
    assert set(PLANNER_TABLES) == set(statements) - {"decision_cycle"}
