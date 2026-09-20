"""Gate item 2 — the Orchestrator performs no direct DB table mutation.

docs/IMPLEMENTATION_PLAN.md §2 Gate: "Orchestrator 无 direct DB table
mutation." Realized here as an import-dependency + call-surface scan over
src/elc/runtime/**: the orchestrator package may not import sqlite3 or any
elc.platform.db module, may not call execute/executemany/executescript/
commit/rollback, and may not carry SQL text at all. Coordination flows only
through domain command/query interfaces (docs/DOMAIN_MODEL.md §16, D-INV-001).
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

from tests.conftest import SRC_ROOT

RUNTIME_ROOT = SRC_ROOT / "runtime"

_FORBIDDEN_IMPORT_MODULES = {"sqlite3"}
_FORBIDDEN_DB_PREFIXES = ("elc.platform.db",)
_FORBIDDEN_CALL_ATTRIBUTES = {
    "execute",
    "executemany",
    "executescript",
    "commit",
    "rollback",
}
_SQL_KEYWORD_MARKERS = ("insert into", "update ", "delete from", "create table")


def _python_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.py"))


def test_runtime_package_never_imports_db_machinery() -> None:
    offenders: list[str] = []
    for path in _python_files(RUNTIME_ROOT):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_name = alias.name.split(".")[0]
                    if alias.name in _FORBIDDEN_IMPORT_MODULES or root_name in (
                        "sqlite3",
                    ):
                        offenders.append(f"{path.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module in _FORBIDDEN_IMPORT_MODULES or module.startswith(
                    _FORBIDDEN_DB_PREFIXES
                ):
                    offenders.append(f"{path.name}: from {module} import …")
    assert not offenders, f"runtime package touches DB machinery: {offenders}"


def test_runtime_package_has_no_sql_call_surface() -> None:
    offenders: list[str] = []
    for path in _python_files(RUNTIME_ROOT):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            # Any attribute call named execute/commit/… — regardless of receiver.
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in _FORBIDDEN_CALL_ATTRIBUTES:
                    offenders.append(f"{path.name}:{node.lineno} .{node.func.attr}()")
            # SQL text anywhere in string constants.
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                lowered = node.value.lower()
                if any(marker in lowered for marker in _SQL_KEYWORD_MARKERS):
                    offenders.append(f"{path.name}:{node.lineno} SQL literal")
    assert not offenders, f"runtime package carries a DB call surface: {offenders}"


def test_runtime_coordinates_through_domain_interfaces() -> None:
    """Positive face: the orchestrator coordinates via domain Commands
    interfaces, which exist as separate authority boundaries (Gate item 1);
    the runtime package exposes its own coordination protocol only."""
    from elc.conversation import ConversationCommands
    from elc.learning import LearningCommands
    from elc.planner import PlannerCommands
    from elc.runtime import RuntimeCommands, RuntimeOrchestrator
    from elc.teaching import TeachingCommands

    for commands in (
        ConversationCommands,
        LearningCommands,
        PlannerCommands,
        TeachingCommands,
    ):
        assert inspect.isclass(commands)
    assert inspect.isclass(RuntimeCommands)
    assert inspect.isclass(RuntimeOrchestrator)
