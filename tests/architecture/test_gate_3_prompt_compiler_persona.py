"""Gate item 3 — PromptCompiler exists only inside Persona Runtime.

docs/IMPLEMENTATION_PLAN.md §2 Gate: "PromptCompiler 仅存在 Persona
Runtime." Enforced over the whole src tree via AST: any class definition
named PromptCompiler must live under elc/persona/, and any import of that
name must come from an elc.persona module (docs/DOMAIN_MODEL.md D-INV-012).
"""

from __future__ import annotations

import ast
from pathlib import Path

from tests.conftest import SRC_ROOT

_COMPILER_CLASS = "PromptCompiler"


def _python_files() -> list[Path]:
    return sorted(SRC_ROOT.rglob("*.py"))


def test_prompt_compiler_class_defined_only_in_persona() -> None:
    offenders: list[str] = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == _COMPILER_CLASS:
                rel = path.relative_to(SRC_ROOT).as_posix()
                if not rel.startswith("persona/"):
                    offenders.append(f"{rel}:{node.lineno} defines {_COMPILER_CLASS}")
    assert not offenders, f"PromptCompiler defined outside Persona Runtime: {offenders}"


def test_prompt_compiler_imported_only_from_persona() -> None:
    offenders: list[str] = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
                hits = [n for n in names if n.split(".")[-1] == _COMPILER_CLASS]
                modules = hits
            else:
                modules = [
                    f"{node.module}.{alias.name}"
                    for alias in node.names
                    if alias.name == _COMPILER_CLASS
                ]
            for module in modules:
                if not module.startswith(("elc.persona", "elc.persona.commands")):
                    rel = path.relative_to(SRC_ROOT).as_posix()
                    offenders.append(f"{rel}:{node.lineno} imports {module}")
    assert not offenders, (
        f"PromptCompiler imported outside Persona Runtime: {offenders}"
    )
