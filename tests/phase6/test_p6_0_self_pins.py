"""P6-0 ⑥ — the suite's own red lines, made checkable.

Two claims this slice makes about itself, both AST-scanned over its own
files:

- **no fixture supply and no seed.** The Phase 3 fixture target provider is
  the one thing P5-0/P5-1 replaced with the real content.db chain; a P6-0
  test that imported it (or that grew a ``_seed``-style helper) would be
  asserting a world the product cannot build. ``tests.phase3.sql_write_scan``
  is deliberately still importable: it is a read-only AST helper the P3/P4
  architecture pins already use and it carries no fixture supply;
- **the fixtures build the world through the shipped chain.** The phase 6
  conftest — this suite's fixture supply — contains no SQL write statement
  at all: its app.db comes from ``elc.platform.db.migrations`` and its rows
  from the stores under test, so a hand-written schema or a hand-inserted
  row cannot pass for the shipped world. The scan below covers that
  conftest; the suite's one deliberate raw-row writer is the pre-0011
  lineage fixture of the migration test, which hand-builds the *input* of
  the upgrade (the v10 world as it was) and is asserted as a lineage, never
  as the shipped chain.
"""

from __future__ import annotations

import ast
from pathlib import Path

from tests.phase3.sql_write_scan import write_targets_from_source

PHASE6_DIR = Path(__file__).resolve().parent
CONFTEST = PHASE6_DIR / "conftest.py"


def _imported_modules(source: str) -> list[str]:
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    return imported


def _called_names(source: str) -> list[str]:
    tree = ast.parse(source)
    calls: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.append(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.append(node.func.attr)
    return calls


def test_the_phase_6_modules_neither_seed_nor_import_the_fixture_supply() -> None:
    modules = sorted(PHASE6_DIR.glob("*.py"))
    assert len(modules) >= 6
    for path in modules:
        source = path.read_text(encoding="utf-8")
        imported = _imported_modules(source)
        assert not [
            module for module in imported if "target_fixtures" in module
        ], path.name
        assert "tests.phase3" not in imported, path.name
        assert not [
            module
            for module in imported
            if module.startswith("tests.phase3.conftest")
        ], path.name
        assert "_seed" not in _called_names(source), path.name
        print(f"[p6-0] {path.name}: imports/calls are clean")


def test_the_phase_6_fixtures_contain_no_hand_written_schema_or_rows() -> None:
    """The conftest's world is built by migrations + the shipped stores: no
    INSERT/UPDATE/DELETE statement literal appears in it, and the schema it
    opens is the migration runner's.

    The scan covers the conftest, which is where this suite's world-building
    fixtures live; the migration test's pre-0011 rows are the upgrade's
    *input*, not a fixture (module docstring).
    """

    source = CONFTEST.read_text(encoding="utf-8")
    assert write_targets_from_source(source) == set()
    assert "migrations.apply_migrations" in source
    assert "build_content_db" in source
    for forbidden in ("CREATE TABLE", "INSERT INTO", "DROP TABLE"):
        assert forbidden not in source, forbidden
