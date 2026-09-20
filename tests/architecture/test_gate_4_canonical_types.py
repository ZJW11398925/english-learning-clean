"""Gate item 4 — canonical IDs / version fields are unified.

docs/IMPLEMENTATION_PLAN.md §2 Gate: "canonical IDs / version fields 统一."
- `NewType` aliases are defined exactly once, in elc.platform.types;
- the canonical version-field vocabulary from docs/DATA_MODEL.md §1.4 is
  pinned in VERSION_FIELDS;
- domain packages may re-export these names but re-exported identity is the
  platform object (spot-checked for every domain package);
- turn/message sequences and distinct IDs are pairwise distinct types.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import NewType

import elc.platform.types as platform_types
from tests.conftest import DOMAIN_PACKAGES, SRC_ROOT

import importlib


def _python_files() -> list[Path]:
    return sorted(SRC_ROOT.rglob("*.py"))


def test_newtype_defined_only_in_platform_types() -> None:
    offenders: list[str] = []
    for path in _python_files():
        rel = path.relative_to(SRC_ROOT).as_posix()
        if rel == "platform/types.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "NewType"
            ):
                offenders.append(f"{rel}:{node.lineno}")
    assert not offenders, f"NewType defined outside elc/platform/types.py: {offenders}"


def test_canonical_version_fields_pinned() -> None:
    """docs/DATA_MODEL.md §1.4 version-everything list."""
    required = {
        "estimator_version",
        "planner_version",
        "policy_version",
        "evaluator_version",
        "validator_version",
        "content_version",
        "curriculum_version",
    }
    missing = required - set(platform_types.VERSION_FIELDS)
    assert not missing, f"VERSION_FIELDS missing canonical fields: {missing}"
    for name, type_ in platform_types.VERSION_FIELDS.items():
        assert type_ is not None
        assert type(getattr(platform_types, type_.__name__)) is NewType


def test_domain_reexports_are_platform_identity() -> None:
    """Every ID/version type a domain re-exports IS the platform definition."""
    platform_attrs = vars(platform_types)
    mismatches: list[str] = []
    for package in DOMAIN_PACKAGES:
        module = importlib.import_module(f"elc.{package}")
        for name in getattr(module, "__all__", []):
            exported = getattr(module, name)
            if name in platform_attrs and _is_newtype(platform_attrs[name]):
                if exported is not platform_attrs[name]:
                    mismatches.append(f"elc.{package}.{name}")
    assert not mismatches, f"re-export drift from platform types: {mismatches}"


def _is_newtype(obj: object) -> bool:
    return type(obj) is NewType


def test_sequence_and_id_types_pairwise_distinct() -> None:
    assert platform_types.TurnSequence is not platform_types.MessageSequence
    assert platform_types.ConversationId is not platform_types.PersonaId
    assert platform_types.TargetId is not platform_types.ResourceId
