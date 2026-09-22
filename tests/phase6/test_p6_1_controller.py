"""P6-1 ②④ — the authority face: the graduated writes, the reads, and the two
declarations that stay behind a P6-2 pointer.

What is pinned here is the shape of the graduation (the teaching /
relationship / user_config precedent):

- the four implemented faces **delegate** and hold no rule of their own: the
  controller's module writes to no table (AST scan), and inspecting each
  method's source finds no ``NotImplementedError``;
- exactly two public methods still raise — ``get_schedule_view`` (DOMAIN_MODEL
  §10, the Planner's input view) and ``is_review_due`` (D-INV-009, the due
  decision) — and both raise the **same P6-2 pointer** constant;
- the Phase 0 faces are gone: ``record_review_outcome`` (no ``retrieved`` in
  the canonical vocabulary), ``suspend_review`` (no ``SUSPENDED`` state and no
  ``reason`` column) and ``get_review_state`` (the skeleton record §5.2
  replaces);
- the two protocols match the face they describe, and the shipped controller
  and store satisfy both of them.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import get_type_hints

from elc.platform.types import EvidenceModality, Ok, TargetId
from elc.scheduler import __all__ as PACKAGE_EXPORTS
from elc.scheduler.commands import SchedulerCommands
from elc.scheduler.controller import (
    P6_2_DUE_DECISION_POINTER,
    SchedulerController,
)
from elc.scheduler.queries import SchedulerQueries
from elc.scheduler.store import SqliteSchedulerStore
from elc.scheduler.types import ReviewState
from tests.conftest import SRC_ROOT
from tests.phase3.sql_write_scan import write_targets

from .conftest import MODALITY, TARGET_ID, TARGET_TYPE, review_event, schedule_item

CONTROLLER_MODULE = SRC_ROOT / "scheduler" / "controller.py"

IMPLEMENTED_FACES = (
    "upsert_schedule_item",
    "record_review_event",
    "get_schedule_item",
    "list_review_events",
)
P6_2_FACES = ("get_schedule_view", "is_review_due")
REMOVED_FACES = ("record_review_outcome", "suspend_review", "get_review_state")


def _public_methods() -> dict[str, object]:
    return {
        name: member
        for name, member in inspect.getmembers(
            SchedulerController, inspect.isfunction
        )
        if not name.startswith("_")
    }


# -- the graduation ----------------------------------------------------------


def test_the_implemented_faces_raise_nothing() -> None:
    for name in IMPLEMENTED_FACES:
        source = inspect.getsource(getattr(SchedulerController, name))
        assert "NotImplementedError" not in source, name


def test_only_the_two_p6_2_faces_raise() -> None:
    """The graduation is exhaustive, not partial: every public method is
    either implemented or one of the two pointed declarations."""

    methods = _public_methods()
    assert sorted(methods) == sorted(IMPLEMENTED_FACES + P6_2_FACES)
    raising = {
        name
        for name in methods
        if "NotImplementedError" in inspect.getsource(methods[name])
    }
    assert raising == set(P6_2_FACES)


def test_the_two_declarations_raise_the_p6_2_pointer() -> None:
    for name in P6_2_FACES:
        source = inspect.getsource(getattr(SchedulerController, name))
        assert "NotImplementedError(P6_2_DUE_DECISION_POINTER)" in source, name
    for call in (
        ("get_schedule_view", ("scope",)),
        ("is_review_due", (TARGET_TYPE, TARGET_ID, MODALITY, "now")),
    ):
        try:
            getattr(SchedulerController, call[0])(object(), *call[1])
        except NotImplementedError as exc:
            assert str(exc) == P6_2_DUE_DECISION_POINTER
        else:  # pragma: no cover - the assertion is the point
            raise AssertionError(f"{call[0]} must raise the P6-2 pointer")


def test_the_pointer_names_the_phase_and_both_canonical_anchors() -> None:
    assert P6_2_DUE_DECISION_POINTER.startswith("P6-2:")
    for phrase in ("DOMAIN_MODEL.md §9", "§10"):
        assert phrase in P6_2_DUE_DECISION_POINTER, phrase


def test_the_removed_phase_zero_faces_are_gone() -> None:
    """Not renamed, not re-pointed: §5.2 has no ``retrieved`` column, no
    ``SUSPENDED`` state and no ``reason`` column, and the skeleton's record
    type is replaced by ScheduleItem."""

    methods = set(_public_methods())
    for name in REMOVED_FACES:
        assert name not in methods, name
    source = CONTROLLER_MODULE.read_text(encoding="utf-8")
    for word in ("record_review_outcome", "suspend_review"):
        assert f"def {word}" not in source, word


def test_the_controller_takes_exactly_one_collaborator() -> None:
    parameters = inspect.signature(SchedulerController.__init__).parameters
    assert list(parameters) == ["self", "store"]


def test_the_controller_carries_no_sql() -> None:
    assert write_targets(CONTROLLER_MODULE) == set()
    source = CONTROLLER_MODULE.read_text(encoding="utf-8")
    for token in (".execute(", ".commit(", ".rollback("):
        assert token not in source, token


def test_the_delegation_is_one_call_per_face() -> None:
    """Each implemented face forwards to the store's same-named method — the
    rule lives there, and this face adds none of its own."""

    tree = ast.parse(CONTROLLER_MODULE.read_text(encoding="utf-8"))
    forwards: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name not in (
            IMPLEMENTED_FACES
        ):
            continue
        calls = [
            inner.func.attr
            for inner in ast.walk(node)
            if isinstance(inner, ast.Call)
            and isinstance(inner.func, ast.Attribute)
        ]
        forwards[node.name] = calls[-1] if calls else ""
    assert forwards == {name: name for name in IMPLEMENTED_FACES}


# -- the faces behave --------------------------------------------------------


def test_the_write_faces_return_the_durable_row(
    scheduler_controller: SchedulerController,
) -> None:
    written = scheduler_controller.upsert_schedule_item(
        schedule_item(review_state=ReviewState.DUE)
    )
    assert isinstance(written, Ok), written
    read = scheduler_controller.get_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY
    )
    assert isinstance(read, Ok) and read.value is not None
    assert read.value == written.value
    # A replay of the same content is the same durable value, not a new one.
    replay = scheduler_controller.upsert_schedule_item(
        schedule_item(review_state=ReviewState.DUE)
    )
    assert isinstance(replay, Ok)
    assert replay.value == written.value


def test_a_refusal_travels_through_the_controller_unchanged(
    scheduler_controller: SchedulerController,
) -> None:
    assert isinstance(
        scheduler_controller.upsert_schedule_item(schedule_item()), Ok
    )
    refused = scheduler_controller.upsert_schedule_item(
        schedule_item(review_state=ReviewState.OVERDUE)
    )
    assert not isinstance(refused, Ok)
    assert refused.error.code.value == "CONFLICT"
    read = scheduler_controller.get_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY
    )
    assert isinstance(read, Ok) and read.value is not None
    assert read.value.review_state is ReviewState.UPCOMING


def test_the_event_faces_delegate_both_ways(
    scheduler_controller: SchedulerController,
) -> None:
    assert isinstance(
        scheduler_controller.upsert_schedule_item(schedule_item()), Ok
    )
    written = scheduler_controller.record_review_event(
        review_event("re-1", created_at="2026-09-22T10:00:00+00:00")
    )
    assert isinstance(written, Ok), written
    history = scheduler_controller.list_review_events("si-1")
    assert isinstance(history, Ok)
    assert history.value == (written.value,)
    missing = scheduler_controller.record_review_event(
        review_event("re-2", schedule_item_id="si-ghost")
    )
    assert not isinstance(missing, Ok)
    assert missing.error.code.value == "NOT_FOUND"


def test_the_reads_answer_none_before_any_write(
    scheduler_controller: SchedulerController,
) -> None:
    read = scheduler_controller.get_schedule_item(
        TARGET_TYPE, TargetId("res-nowhere"), MODALITY
    )
    assert isinstance(read, Ok)
    assert read.value is None
    history = scheduler_controller.list_review_events("si-absent")
    assert isinstance(history, Ok)
    assert history.value == ()


# -- the declared interfaces -------------------------------------------------


def test_the_commands_protocol_declares_the_two_writes() -> None:
    declared = {
        name
        for name, member in vars(SchedulerCommands).items()
        if not name.startswith("_") and inspect.isfunction(member)
    }
    assert declared == {"upsert_schedule_item", "record_review_event"}


def test_the_queries_protocol_declares_the_four_reads() -> None:
    declared = {
        name
        for name, member in vars(SchedulerQueries).items()
        if not name.startswith("_") and inspect.isfunction(member)
    }
    assert declared == {
        "get_schedule_item",
        "list_review_events",
        "get_schedule_view",
        "is_review_due",
    }


def test_is_review_due_is_keyed_by_the_modality_key() -> None:
    """The Phase 0 spelling took ``target_id`` alone; a §5.2 row cannot be
    found without the evidence modality its key carries, so the declaration
    (and the controller's method) carry the whole key."""

    for face in (SchedulerQueries.is_review_due, SchedulerController.is_review_due):
        parameters = list(inspect.signature(face).parameters)
        assert parameters == [
            "self",
            "target_type",
            "target_id",
            "evidence_modality",
            "at",
        ] or parameters == ["target_type", "target_id", "evidence_modality", "at"]


def test_both_faces_declare_the_evidence_modality_type() -> None:
    hints = get_type_hints(SchedulerController.get_schedule_item)
    assert hints["evidence_modality"] is EvidenceModality
    assert hints["target_id"] is TargetId
    assert hints["target_type"] is str


def test_the_shipped_faces_satisfy_the_protocols(
    scheduler_controller: SchedulerController,
    scheduler_store: SqliteSchedulerStore,
) -> None:
    """``runtime_checkable``: the structural promise the Phase 0 interfaces
    made is kept by the shipped objects. The controller answers both faces
    (including the two P6-2 declarations); the store answers the command face
    and the two durable reads — it deliberately has no ``get_schedule_view`` /
    ``is_review_due``, because a due decision is not a row read."""

    assert isinstance(scheduler_controller, SchedulerCommands)
    assert isinstance(scheduler_controller, SchedulerQueries)
    assert isinstance(scheduler_store, SchedulerCommands)
    assert not isinstance(scheduler_store, SchedulerQueries)


def test_the_package_exports_are_complete() -> None:
    """A public module the ``__all__`` does not name is a face a consumer
    cannot find (the teaching review F10 lesson): every name the package
    surfaces is exported, exactly once, in sorted order."""

    expected = {
        "P6_2_DUE_DECISION_POINTER",
        "REVIEW_EVENT_TABLE",
        "REVIEW_STATES",
        "SCHEDULE_ITEM_TABLE",
        "ReviewEvent",
        "ReviewState",
        "ScheduleItem",
        "ScheduleView",
        "SchedulerCommands",
        "SchedulerController",
        "SchedulerQueries",
        "SpacingStage",
        "SqliteSchedulerStore",
        "StaleSchedulerStoreError",
    }
    assert set(PACKAGE_EXPORTS) == expected
    assert len(PACKAGE_EXPORTS) == len(set(PACKAGE_EXPORTS))
    assert list(PACKAGE_EXPORTS) == sorted(PACKAGE_EXPORTS)


def test_every_export_resolves() -> None:
    import elc.scheduler as package

    for name in PACKAGE_EXPORTS:
        assert getattr(package, name) is not None, name
    assert Path(package.__file__).name == "__init__.py"
    assert package.SchedulerController is SchedulerController
    assert package.SqliteSchedulerStore is SqliteSchedulerStore
