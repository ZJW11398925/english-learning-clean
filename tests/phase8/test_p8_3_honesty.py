"""P8-3 ⑦⑧⑨ — the flip, the two texts, and what this cut does **not** claim.

``PLANNING_LEDGER_STORAGE_REVISIT`` named the condition ("land the table in the
same change *and* its statements in the BF-05 deletion walk"); this cut
satisfies it, and the pins here hold the three claims that make the flip
honest rather than a word change:

- the tables exist **and** both deletion legs name them (the condition as a
  checkable conjunction, not as prose);
- the old word is kept (a state this repository really had) and the new
  revisit names what re-opens the *new* decision;
- no shipped face writes the ledger yet — the producer is p8-4's — so the
  cut's registrations say so everywhere the reader meets them.
"""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

from elc.deletion.types import (
    LEARNING_HISTORY_SWEPT_TABLES,
    LEARNING_TARGET_SWEPT_TABLES,
    SWEPT_TABLES,
)
from elc.planner.ledger import (
    PLANNING_LEDGER_MODEL_VERSION,
    PLANNING_LEDGER_STORAGE,
    PLANNING_LEDGER_STORAGE_REVISIT,
    LedgerStorage,
    PlanningLedger,
)
from elc.planner.ledger_store import PLANNING_LEDGER_STORE_SOURCES
from elc.planner.types import PlanningRequest
from elc.platform.registry import (
    CANONICAL_OBJECTS,
    OWNER_PLANNER,
)
from tests.conftest import REPO_ROOT, SRC_ROOT

LEDGER_MODULE = SRC_ROOT / "planner" / "ledger.py"
STORE_MODULE = SRC_ROOT / "planner" / "ledger_store.py"
PACKAGE_MODULE = SRC_ROOT / "planner" / "__init__.py"
MIGRATION = REPO_ROOT / "migrations" / "0016_planning_ledger.sql"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# -- ⑧ the flip --------------------------------------------------------------


def test_the_storage_word_moved_and_the_old_word_stayed() -> None:
    assert PLANNING_LEDGER_STORAGE is LedgerStorage.DURABLE_TABLES_V1
    assert {word.value for word in LedgerStorage} == {
        "NO_TABLE_V1",
        "DURABLE_TABLES_V1",
    }


def test_the_revisit_condition_is_satisfied_by_this_cut(
    db,
) -> None:
    """The conjunction the old constant named, checked rather than asserted:
    the tables exist in a migrated app.db *and* both BF-05 scopes name them."""

    tables = {
        str(row[0])
        for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    for table in PLANNING_LEDGER_STORE_SOURCES:
        assert table in tables, table
        assert table in SWEPT_TABLES, table
        assert table in LEARNING_TARGET_SWEPT_TABLES, table
        assert table in LEARNING_HISTORY_SWEPT_TABLES, table


def test_the_new_revisit_names_what_re_opens_it() -> None:
    text = PLANNING_LEDGER_STORAGE_REVISIT
    assert "landed" in text
    assert "Phase 8" in text and "P8-3" in text
    assert "deletion" in text
    assert "LEARNING_TARGET" in text and "LEARNING_HISTORY" in text
    assert "re-opening" in text or "reopening" in text
    assert "p8-4" in text
    assert "NO_TABLE_V1" not in text
    assert "no table" not in text.lower()


def test_the_model_version_is_unchanged() -> None:
    """The cut lands storage; the core's declared readings are not re-versioned."""

    assert PLANNING_LEDGER_MODEL_VERSION == "pl1"


def test_the_core_module_says_the_table_landed_and_keeps_its_arguments() -> None:
    text = " ".join(_source(LEDGER_MODULE).split())
    assert "The table landed (P8-3)" in text
    assert "no writer" in text
    assert "PlanningLedger user history" in text
    assert "some PlanningLedger rollups" in text
    assert "SELECT != exposure" in text


def test_the_core_view_names_the_durable_half_instead_of_the_retired_word() -> None:
    """The two prose references that still pointed at ``NO_TABLE_V1`` as a live
    fact (p8-3 disposal F2) now name the current one: this class carries no
    store, and the durable half is ``elc.planner.ledger_store`` under
    ``DURABLE_TABLES_V1``. Read off the AST, so it is the docstrings that are
    checked and not some other copy of the words."""

    tree = ast.parse(_source(LEDGER_MODULE))
    ledger_class = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == "PlanningLedger"
    )
    record_event = next(
        node
        for node in ledger_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "record_event"
    )
    for owner, doc in (
        ("PlanningLedger", ast.get_docstring(ledger_class) or ""),
        ("record_event", ast.get_docstring(record_event) or ""),
    ):
        assert doc, owner
        assert "NO_TABLE_V1" not in doc, owner
        assert "ledger_store" in doc, owner
        assert "DURABLE_TABLES_V1" in doc, owner


def test_the_store_module_registers_the_missing_producer() -> None:
    text = " ".join(_source(STORE_MODULE).split())
    assert "No producer, registered rather than implied" in text
    assert "p8-4" in text
    assert "SELECT != exposure" in text
    assert "shipped caller count is zero" in text


def test_the_ledger_is_registered_with_an_owner_and_no_invented_version() -> None:
    entry = CANONICAL_OBJECTS["planning_ledger"]
    assert entry.name == "PlanningLedger"
    assert entry.owner == OWNER_PLANNER
    assert entry.schema is PlanningLedger
    assert entry.version_field is None


def test_the_two_rollup_columns_are_nowhere_in_the_schema_or_a_statement() -> None:
    """Not materialized is a fact about the DDL and about every statement the
    store carries — the prose explains the reading, and neither column reaches
    a statement (the read face answers the core's defaults)."""

    ddl = "\n".join(
        line
        for line in _source(MIGRATION).splitlines()
        if not line.lstrip().startswith("--")
    )
    for column in ("coverage_debt_rollups", "recent_target_families"):
        assert column not in ddl, column
        tree = ast.parse(_source(STORE_MODULE))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant):
                continue
            if not isinstance(node.value, str):
                continue
            head = node.value.lstrip().upper()
            if not head.startswith(("SELECT", "INSERT")):
                continue  # prose, not a statement
            assert column not in node.value, (column, node.lineno)


# -- ⑨ no shipped caller -----------------------------------------------------


def test_no_src_module_imports_the_ledger_store() -> None:
    """The producer is p8-4's: today the store has exactly one importer that is
    not a test — itself."""

    importers: list[str] = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        if path == STORE_MODULE:
            continue
        tree = ast.parse(_source(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            if any("ledger_store" in name for name in names):
                importers.append(path.name)
    assert importers == []


def test_the_store_is_not_exported_from_the_package() -> None:
    """The ``planner_store`` / ``stress_suite`` precedent: the SQL adapter is
    reachable by import, not re-exported as the package's face."""

    text = _source(PACKAGE_MODULE)
    tree = ast.parse(text)
    exported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    exported = [
                        element.value
                        for element in node.value.elts  # type: ignore[attr-defined]
                    ]
    assert "ledger_store" not in exported
    assert "SqliteLedgerStore" not in exported
    assert "ledger_store" in text  # the docstring points at it


def test_the_planner_request_gained_no_field() -> None:
    """A request that could carry the ledger already does (P7-4's shape); this
    cut lands the storage, not a new input."""

    names = tuple(field.name for field in dataclasses.fields(PlanningRequest))
    assert names == (
        "decision_cycle_id",
        "learning_snapshot",
        "curriculum_candidate_view",
        "schedule_view",
        "goal_view",
        "teaching_policy_view",
        "context_opportunity_set",
        "planner_constraint_view",
        "session_budget_view",
        "user_intent_scope",
        "conversation_priority_view",
        "planning_ledger",
    )


def test_the_unlanded_authority_text_no_longer_denies_the_ledger() -> None:
    """``UNLANDED_AUTHORITIES[PLANNING_LEDGER]``'s literal expired before this
    cut (p7-3 registered that its meaning moved to the ledger module); P8-3
    makes the text true instead of obsolete."""

    from elc.planner.candidates import UNLANDED_AUTHORITIES, CandidateAuthority

    text = UNLANDED_AUTHORITIES[CandidateAuthority.PLANNING_LEDGER]
    assert "p7-3's work item" not in text
    assert "durable since P8-3" in text
    assert "0016" in text
    assert "ledger_store" in text
    assert "p8-4" in text
    assert len(text) > 60


def test_the_gap_text_still_travels_with_a_missing_ledger_view() -> None:
    """The entry is still the reason a source gaps when no view is handed in —
    the phase-7 chain test's own equality, re-asserted from this side."""

    from elc.planner.candidates import (
        UNLANDED_AUTHORITIES,
        CandidateAuthority,
    )

    assert CandidateAuthority.PLANNING_LEDGER in UNLANDED_AUTHORITIES
    assert set(UNLANDED_AUTHORITIES) == {
        CandidateAuthority.TRANSFER_POLICY,
        CandidateAuthority.CORE_TIER,
        CandidateAuthority.GOAL_PACK_MAPPING,
        CandidateAuthority.PLANNING_LEDGER,
    }


def test_the_cut_added_no_other_table_to_the_ledger() -> None:
    """The three tables are the whole durable ledger: a fourth would move the
    source tuple, the walk and the migration together (the tuple's docstring)."""

    assert PLANNING_LEDGER_STORE_SOURCES == (
        "planning_ledger",
        "coverage_obligation",
        "planning_ledger_event",
    )
    text = _source(MIGRATION)
    assert text.count("CREATE TABLE IF NOT EXISTS") == 3
