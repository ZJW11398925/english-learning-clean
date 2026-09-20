"""Gate item 5 — canonical objects have owner + schema.

docs/IMPLEMENTATION_PLAN.md §2 Gate: "Goal/Policy/Profile/Scheduler/Gate/
Validator/Projection 等 canonical object 均有 owner/schema." The registry in
elc.platform.registry is the machine-checkable form: each entry names one
owner (an existing elc package) and one schema type; versioned entries use a
canonical VERSION_FIELDS spelling.
"""

from __future__ import annotations

import importlib

import pytest

from elc.platform.registry import CANONICAL_OBJECTS
from elc.platform.types import VERSION_FIELDS

# Gate categories → registry keys (docs/DOMAIN_MODEL.md §2 Authority Matrix).
GATE_CATEGORY_KEYS = {
    "Goal": "goal_portfolio",
    "Policy": "teaching_policy",
    "Profile": "user_profile",
    "Scheduler": "schedule_view",
    "Gate": "gate_decision",
    "Validator": "validator_result",
    "Projection": "projection_job",
}


@pytest.mark.parametrize("category,key", sorted(GATE_CATEGORY_KEYS.items()))
def test_gate_category_has_owner_and_schema(category: str, key: str) -> None:
    assert key in CANONICAL_OBJECTS, f"{category} missing from registry"
    entry = CANONICAL_OBJECTS[key]
    assert entry.owner, f"{category} has no owner"
    assert inspectable_schema(entry.schema), f"{category} schema unresolvable"


def inspectable_schema(schema: type) -> bool:
    import inspect

    return inspect.isclass(schema)


def test_every_registered_owner_is_a_real_package() -> None:
    problems = []
    for key, entry in CANONICAL_OBJECTS.items():
        try:
            importlib.import_module(f"elc.{entry.owner}")
        except ImportError as exc:  # pragma: no cover - assertion message only
            problems.append(f"{key}: owner elc.{entry.owner} missing ({exc})")
    assert not problems, problems


def test_registry_version_fields_are_canonical() -> None:
    for key, entry in CANONICAL_OBJECTS.items():
        if entry.version_field is not None:
            assert entry.version_field in VERSION_FIELDS, (
                f"{key} uses non-canonical version field {entry.version_field}"
            )
