"""P6-1 ②⑦ — the suite's own red lines, made checkable.

The same two claims P6-0's self-pin makes, extended over this slice's files,
plus the two this cut adds:

- **no fixture supply and no seed.** The Phase 3 fixture target provider is
  the one thing P5-0/P5-1 replaced with the real content.db chain; a P6-1 test
  that imported it (or that grew a ``_seed``-style helper) would be asserting a
  world the product cannot build. ``tests.phase3.sql_write_scan`` is
  deliberately still importable: it is a read-only AST helper the P3/P4
  architecture pins already use and it carries no fixture supply;
- **the fixtures build the world through the shipped chain.** The phase 6
  conftest — this suite's fixture supply — contains no SQL write statement at
  all: its app.db comes from ``elc.platform.db.migrations`` and its rows from
  the stores under test. The migration tests' pre-00xx rows are the *input* of
  an upgrade (a lineage), never a fixture;
- **nothing is skipped.** The receipt's "0 skipped" is a structural property
  here: no ``skip`` / ``xfail`` mark exists in the suite;
- **every package imports from a cold interpreter** — the P4-3 lesson, applied
  to the packages this slice touches: ``elc.scheduler`` is a new package whose
  ``__init__`` aggregates from four modules, and a domain module that imported
  the package back would break a cold ``import elc.scheduler.store`` while the
  ordered test session never noticed.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

from tests.conftest import REPO_ROOT
from tests.phase3.sql_write_scan import write_targets_from_source

PHASE6_DIR = Path(__file__).resolve().parent
CONFTEST = PHASE6_DIR / "conftest.py"

#: The packages this slice's own work makes reachable, each imported first in a
#: fresh interpreter (tests/phase4/test_p4_3_gates.py's pattern).
COLD_START_PACKAGES = (
    "elc.scheduler",
    "elc.scheduler.store",
    "elc.scheduler.controller",
    "elc.scheduler.types",
    # P6-2's pure policy: a domain module that imported the package back would
    # break a cold ``import elc.scheduler.spacing`` while the ordered test
    # session never noticed (the P4-3 lesson).
    "elc.scheduler.spacing",
    "elc.platform.registry",
    "elc.user_config",
    "elc.learning",
)


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


def _defined_names(source: str) -> list[str]:
    return [
        node.name
        for node in ast.walk(ast.parse(source))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


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
        assert not [
            name
            for name in _defined_names(source)
            if name.startswith("_seed") or name == "_seed"
        ], path.name
        print(f"[p6-1] {path.name}: imports/calls are clean")


def test_the_phase_6_fixtures_contain_no_hand_written_schema_or_rows() -> None:
    """The conftest's world is built by migrations + the shipped stores: no
    INSERT/UPDATE/DELETE statement literal appears in it, and the schema it
    opens is the migration runner's.

    The scan covers the conftest, which is where this suite's world-building
    fixtures live; the migration tests' pre-00xx rows are an upgrade's *input*,
    not a fixture.
    """

    source = CONFTEST.read_text(encoding="utf-8")
    assert write_targets_from_source(source) == set()
    assert "migrations.apply_migrations" in source
    assert "build_content_db" in source
    for forbidden in ("CREATE TABLE", "INSERT INTO", "DROP TABLE"):
        assert forbidden not in source, forbidden


def test_the_conftest_supplies_the_fixtures_this_slice_consumes() -> None:
    """The scheduler world is a conftest fixture like every other store's —
    built over the same real app.db connection and epoch fence."""

    source = CONFTEST.read_text(encoding="utf-8")
    for name in (
        "def scheduler_store(",
        "def scheduler_controller(",
        "def schedule_item(",
        "def review_event(",
    ):
        assert name in source, name
    assert "SqliteSchedulerStore(db, fence)" in source


def _skip_or_xfail_uses(source: str) -> list[str]:
    """Every ``pytest.skip`` call and every ``pytest.mark.skip``-style
    decorator, found through the AST: a text scan would flag this module's own
    list of the names it looks for, and the claim is about *marks*, not
    words."""

    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Attribute) and node.attr in (
            "skip",
            "skipif",
            "xfail",
        ):
            found.append(node.attr)
        elif (
            isinstance(node, ast.Name) and node.id in ("skip", "skipif", "xfail")
        ):
            found.append(node.id)
    return found


def test_the_suite_skips_nothing() -> None:
    """0 skipped is a claim the receipt makes; this pin is what makes it
    structural — no skip/xfail mark exists anywhere in the suite."""

    for path in sorted(PHASE6_DIR.glob("*.py")):
        found = _skip_or_xfail_uses(path.read_text(encoding="utf-8"))
        assert not found, f"{path.name}: {found}"


def test_every_test_module_declares_tests() -> None:
    """No empty placeholder file passes itself off as a suite member — and this
    slice's own files carry the case count the task book asks for."""

    for path in sorted(PHASE6_DIR.glob("test_*.py")):
        tests = [
            name
            for name in _defined_names(path.read_text(encoding="utf-8"))
            if name.startswith("test_")
        ]
        assert tests, path.name
        if path.name.startswith("test_p6_1_"):
            assert len(tests) >= 5, f"{path.name}: {len(tests)}"
        print(f"[p6-1] {path.name}: {len(tests)} test functions")


def test_the_scheduler_package_imports_from_a_cold_interpreter() -> None:
    """The symptom itself, and the strongest form of the pin: a fresh
    interpreter importing one package first must succeed (the P4-3 cold-start
    lesson — an import cycle can hide behind a lucky test-session order)."""

    env = dict(
        os.environ,
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=str(Path(REPO_ROOT) / "src"),
    )
    for package in COLD_START_PACKAGES:
        proc = subprocess.run(
            [sys.executable, "-c", f"import {package}"],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert proc.returncode == 0, f"{package}: {proc.stderr}"


def test_the_scheduler_modules_do_not_import_their_own_package() -> None:
    """The structural half of the cold-start pin: no module under
    ``elc/scheduler/`` imports ``elc.scheduler`` (the package), which is the
    shape an import cycle takes."""

    src_root = Path(REPO_ROOT) / "src" / "elc" / "scheduler"
    for path in sorted(src_root.glob("*.py")):
        for module in _imported_modules(path.read_text(encoding="utf-8")):
            assert module != "elc.scheduler", path.name
