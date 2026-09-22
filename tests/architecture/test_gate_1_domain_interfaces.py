"""Gate item 1 — every domain owns its own command/query interfaces.

docs/IMPLEMENTATION_PLAN.md §2 Gate: "每个 Domain 有 own command/query
interfaces." Each Phase 0 domain package must expose a runtime-checkable
`<X>Commands` write face and `<X>Queries` read face plus an empty Domain
Controller whose methods are declared but unimplemented (Phase 0 = skeleton
only, no domain business logic).
"""

from __future__ import annotations

import importlib
import inspect
from typing import get_type_hints

import pytest

import elc.platform.types as platform_types
from tests.conftest import DOMAIN_PACKAGES


def _protocol_methods(protocol_cls: type) -> dict[str, inspect.Signature]:
    return {
        name: inspect.signature(method)
        for name, method in inspect.getmembers(protocol_cls, inspect.isfunction)
        if not name.startswith("_")
    }


@pytest.mark.parametrize("package", DOMAIN_PACKAGES)
def test_domain_exposes_command_and_query_interfaces(package: str) -> None:
    commands_mod = importlib.import_module(f"elc.{package}.commands")
    queries_mod = importlib.import_module(f"elc.{package}.queries")

    commands = [
        name
        for name, obj in vars(commands_mod).items()
        if inspect.isclass(obj)
        if name.endswith("Commands")
    ]
    queries = [
        name
        for name, obj in vars(queries_mod).items()
        if inspect.isclass(obj)
        if name.endswith("Queries")
    ]
    assert commands, f"elc.{package} lacks a *Commands interface"
    assert queries, f"elc.{package} lacks a *Queries interface"

    # Command/query methods must carry full type signatures (Phase 0 rule).
    for module, names in ((commands_mod, commands), (queries_mod, queries)):
        for cls_name in names:
            cls = getattr(module, cls_name)
            methods = _protocol_methods(cls)
            assert methods, f"{package}.{cls_name} has no interface methods"
            for method_name, signature in methods.items():
                hints = get_type_hints(getattr(cls, method_name))
                assert "return" in hints, (
                    f"{package}.{cls_name}.{method_name} lacks return annotation"
                )
                for param in signature.parameters:
                    if param == "self":
                        continue
                    assert param in hints, (
                        f"{package}.{cls_name}.{method_name} parameter "
                        f"'{param}' lacks annotation"
                    )


@pytest.mark.parametrize("package", DOMAIN_PACKAGES)
def test_domain_controller_is_empty_skeleton(package: str) -> None:
    """Phase 0 red line: no domain business logic — every controller method
    raises NotImplementedError. `infra_allowlist` names the few platform
    infrastructure hooks a controller may already wire (they touch no domain
    truth); `phase1_class_allowlist` names the Phase 1 pipeline classes that
    graduated from the skeleton (they coordinate through domain interfaces
    only — Gate 2 still proves they carry no SQL/DB surface)."""
    infra_allowlist: dict[str, set[str]] = {
        # Startup fence adoption is platform infra, not domain logic.
        "runtime": {"open_startup_fence"},
    }
    phase1_class_allowlist: dict[str, set[str]] = {
        # P1B (TASK-OPI-d7937fd7.9 ⑥): the minimum turn-loop facade —
        # guard + CP0 + persona pipeline + buffered validated delivery,
        # sequencing only, never truth (DOMAIN_MODEL §16).
        "runtime": {"ConversationCoordinator"},
        # P3-0 (TASK-OPI-eaaa5a1d-7ac7-4746-bcdf-c02bc9147492.55 ②):
        # LearningController graduated from the skeleton as the domain
        # authority face — pure delegation to SqliteLearningStore (the
        # durable kernel keeps all truth and SQL); Phase 3 consumers go
        # through it. Same graduation mechanism as the P1B entry above.
        "learning": {"LearningController"},
        # P3-1A (TASK-OPI-2babb21e-….17 ③④): TeachingController graduated
        # as the Teaching authority face — the Gate profile is pure
        # (elc.teaching.gate), the CP2 five-fact unit and all SQL live in
        # elc.teaching.store, and the methods P3-1B/Phase 8 own
        # (record_attempt / terminalize_moment / …) still raise
        # NotImplementedError with a phase pointer.
        "teaching": {"TeachingController"},
        # P4-1 (TASK-OPI-5ba74efc-….100 ②③④⑤): RelationshipController
        # graduated as the Relationship authority face — validate/dedupe and
        # the BF-05 gate are pure modules (elc.relationship.validation /
        # .sensitivity), the durable rows and all SQL live in
        # elc.relationship.store, and the two frozen Phase 0 shapes that
        # cannot carry a complete write (supersede_memory / get_memory) still
        # raise NotImplementedError with a pointer.
        "relationship": {"RelationshipController"},
        # P4-3 (TASK-OPI-4d516e4f-….19 ③④): UserConfigController graduated
        # as the User Configuration/Profile authority face — the §18.1
        # sensitive-persistence gate is in the controller, the pure
        # disclosure ladder is elc.user_config.disclosure, the durable rows
        # and all SQL live in elc.user_config.store. P6-0
        # (TASK-OPI-a68fd9eb-….48 ④) graduated the three faces that used to
        # raise a phase pointer (goal portfolio / teaching policy / session
        # focus), so no method of this controller carries the Phase 0 red
        # line any more; the Scheduler views stay for the later cuts.
        "user_config": {"UserConfigController"},
        # P6-1 (TASK-OPI-6259f6fd-….12 ②④; VAL-OPI-6259f6fd-….10): the
        # SchedulerController graduated as the Scheduler authority face for
        # §5.2's ScheduleItem / ReviewEvent — pure delegation to
        # SqliteSchedulerStore (the durable rows and all SQL live there,
        # migration 0012). Two declarations deliberately still raise, each
        # with a **P6-2 pointer** rather than the Phase 0 red line:
        # get_schedule_view (DOMAIN_MODEL §10 — the Planner's input view) and
        # is_review_due (D-INV-009 — the due decision), both owned by the
        # due/overdue cut.
        "scheduler": {"SchedulerController"},
    }
    allowed = infra_allowlist.get(package, set())
    skipped_classes = phase1_class_allowlist.get(package, set())

    controller_mod = importlib.import_module(f"elc.{package}.controller")
    # Graduated classes count toward module presence (a package whose only
    # controller graduated — learning/LearningController, P3-0 — still has
    # a controller); the NotImplementedError red line below skips them.
    controllers = [
        obj
        for name, obj in vars(controller_mod).items()
        if inspect.isclass(obj)
        if obj.__module__ == controller_mod.__name__
    ]
    assert controllers, f"elc.{package}.controller has no controller class"

    for controller in controllers:
        if controller.__name__ in skipped_classes:
            continue
        for name, member in inspect.getmembers(controller, inspect.isfunction):
            if name.startswith("_") or name in allowed:
                continue
            source = inspect.getsource(member)
            assert "NotImplementedError" in source, (
                f"{controller.__name__}.{name} implements logic — Phase 0 "
                "must stay an empty skeleton"
            )


def test_interface_types_come_from_platform_kernel() -> None:
    """IDs used in interface signatures resolve to the single platform
    definitions (Gate item 4 support): the canonical NewTypes are never
    redefined outside elc.platform.types (checked in
    test_gate_4_canonical_types.py)."""
    assert platform_types.ConversationId is not None
    assert platform_types.TurnSequence is not platform_types.MessageSequence
