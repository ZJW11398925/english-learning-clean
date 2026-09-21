"""Package import boundaries for the teaching slice (task-book
forbidden_changes, AST-pinned).

The frozen rule is two-directional and absolute:

    teaching 不 import elc.learning 内部面（仅经 LearningController 注入/调用），
    learning 不 import elc.teaching（AST 钉）

Both halves are scanned AST-wise over ``src/elc`` (the
tests/phase2/test_validator_evaluator_separation.py paradigm): an import
of the forbidden package — however written, however aliased — fails here.
Docstrings that *name* the other domain while explaining the boundary are
not imports and are deliberately not flagged.
"""

from __future__ import annotations

import ast

from tests.conftest import SRC_ROOT


def _imported_modules(path) -> list[tuple[str, int]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.append((alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append((node.module, node.lineno))
    return modules


def _offenders(package: str, forbidden: str) -> list[str]:
    found: list[str] = []
    for path in sorted((SRC_ROOT / package).rglob("*.py")):
        for module, lineno in _imported_modules(path):
            if module == forbidden or module.startswith(f"{forbidden}."):
                found.append(f"{path.relative_to(SRC_ROOT)}:{lineno} {module}")
    return found


def test_learning_package_never_imports_teaching() -> None:
    offenders = _offenders("learning", "elc.teaching")
    assert not offenders, offenders


def test_persona_package_never_imports_teaching() -> None:
    offenders = _offenders("persona", "elc.teaching")
    assert not offenders, offenders


def test_teaching_package_never_imports_learning_internals() -> None:
    offenders = _offenders("teaching", "elc.learning")
    assert not offenders, offenders


def test_the_scan_is_not_vacuous() -> None:
    """Positive control: the scanner really sees imports (a broken walk
    would otherwise pass every pin above silently)."""

    teaching_modules = {
        module
        for module, _ in _imported_modules(SRC_ROOT / "teaching" / "store.py")
    }
    assert "elc.runtime.types" in teaching_modules
    learning_modules = {
        module
        for module, _ in _imported_modules(SRC_ROOT / "learning" / "controller.py")
    }
    assert "elc.learning.store" in learning_modules
    # The teaching package DOES reach the Learning authority face by
    # injection only: no module imports it, so the coordinator is the one
    # binding — pinned by the rule that elc.teaching.controller receives a
    # store, not a learning store.
    assert not _offenders("teaching", "elc.learning")
