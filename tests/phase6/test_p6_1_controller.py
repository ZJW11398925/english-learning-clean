"""P6-1 ②④ — the authority face: the graduated writes, the reads, and (since
P6-2) the due decision the two declarations used to point at.

What is pinned here is the shape of the graduation (the teaching /
relationship / user_config precedent):

- the four durable faces **delegate** and hold no rule of their own: the
  controller's module writes to no table (AST scan), and inspecting each
  method's source finds no ``NotImplementedError``;
- the three faces P6-1 left declared — ``recompute_schedule_item`` (the due
  decision's write), ``get_schedule_view`` (DOMAIN_MODEL §10, the Planner's
  input view) and ``is_review_due`` (D-INV-009) — are implemented by P6-2, so
  **no public method of this face raises any more** and the P6-2 pointer
  constant the two declarations used to raise with is gone;
- the Phase 0 faces are gone: ``record_review_outcome`` (no ``retrieved`` in
  the canonical vocabulary), ``suspend_review`` (no ``SUSPENDED`` state and no
  ``reason`` column) and ``get_review_state`` (the skeleton record §5.2
  replaces);
- the two protocols match the face they describe (the command face carries the
  §9 recomputation, which is a *decision* and therefore not a store method),
  and the shipped controller satisfies both.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import get_type_hints

import pytest

from elc.platform.types import EvidenceModality, Ok, TargetId
from elc.scheduler import __all__ as PACKAGE_EXPORTS
from elc.scheduler import controller as controller_module
from elc.scheduler.commands import SchedulerCommands
from elc.scheduler.controller import SchedulerController
from elc.scheduler.queries import SchedulerQueries
from elc.scheduler.spacing import SCHEDULER_MODEL_VERSION
from elc.scheduler.store import SqliteSchedulerStore
from elc.scheduler.types import ReviewState
from tests.conftest import SRC_ROOT
from tests.phase3.sql_write_scan import write_targets

from .conftest import MODALITY, TARGET_ID, TARGET_TYPE, review_event, schedule_item

CONTROLLER_MODULE = SRC_ROOT / "scheduler" / "controller.py"

#: The four faces that are pure delegation to the store (one call, same name).
IMPLEMENTED_FACES = (
    "upsert_schedule_item",
    "record_review_event",
    "get_schedule_item",
    "list_review_events",
)
#: The three faces P6-2 implemented: the §9 due decision's write, the §10 view
#: and the due question. They are *decisions* — they call the pure policy in
#: ``elc.scheduler.spacing`` — so they are not one-call delegations.
DUE_DECISION_FACES = (
    "recompute_schedule_item",
    "get_schedule_view",
    "is_review_due",
)
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


def test_no_face_raises_any_more() -> None:
    """The graduation is exhaustive, not partial: every public method is
    implemented — P6-2 filled the last three (the due decision's write, the
    §10 view and the due question) and left no pointer behind."""

    methods = _public_methods()
    assert sorted(methods) == sorted(IMPLEMENTED_FACES + DUE_DECISION_FACES)
    raising = {
        name
        for name in methods
        if "NotImplementedError" in inspect.getsource(methods[name])
    }
    assert raising == set()
    assert "NotImplementedError" not in CONTROLLER_MODULE.read_text(
        encoding="utf-8"
    )


def test_the_due_decision_faces_answer_through_the_store_and_the_policy(
    scheduler_controller: SchedulerController,
) -> None:
    """The three faces P6-1 pointed at now do the work the pointer named: on
    an empty world the view is three empty buckets stamped with the model
    version, ``is_review_due`` is ``False``, and a recomputation without a
    Learning read face refuses in this domain's words instead of raising a
    phase pointer."""

    view = scheduler_controller.get_schedule_view("2026-09-22T09:00:00+00:00")
    assert isinstance(view, Ok), view
    assert view.value.schedule_version == SCHEDULER_MODEL_VERSION
    assert view.value.due_items == ()
    not_due = scheduler_controller.is_review_due(
        TARGET_TYPE, TARGET_ID, MODALITY, "2026-09-22T09:00:00+00:00"
    )
    assert isinstance(not_due, Ok) and not_due.value is False
    homeless = scheduler_controller.recompute_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY, "2026-09-22T09:00:00+00:00"
    )
    assert not isinstance(homeless, Ok)
    assert homeless.error.code.value == "DEPENDENCY_UNAVAILABLE"
    # The decision is the policy's, not a second rule written in this face.
    for name, helper in (
        ("recompute_schedule_item", "plan_schedule_item"),
        ("get_schedule_view", "state_at"),
        ("is_review_due", "state_at"),
    ):
        source = inspect.getsource(getattr(SchedulerController, name))
        assert helper in source, name


def test_the_pointer_constant_is_gone_from_the_module_and_the_package() -> None:
    """The pointer was a declaration that a phase owned a face; the phase
    arrived, so the constant and its references are deleted rather than left
    as a stale marker (the P6-2 scope statement)."""

    assert not hasattr(controller_module, "P6_2_DUE_DECISION_POINTER")
    assert "P6_2_DUE_DECISION_POINTER" not in CONTROLLER_MODULE.read_text(
        encoding="utf-8"
    )
    assert "P6_2_DUE_DECISION_POINTER" not in PACKAGE_EXPORTS
    for path in (SRC_ROOT / "scheduler").rglob("*.py"):
        assert "P6_2_DUE_DECISION_POINTER" not in path.read_text(
            encoding="utf-8"
        ), path.name


def test_the_module_names_the_phase_and_both_canonical_anchors() -> None:
    """The two canonical anchors the deleted pointer named are still declared
    where the faces live: DOMAIN_MODEL §9 (only the Scheduler decides due) and
    §10 (ScheduleView is the Planner's input)."""

    docstring = controller_module.__doc__ or ""
    for phrase in ("DOMAIN_MODEL.md §9", "§10", "P6-2"):
        assert phrase in docstring, phrase


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


def test_the_controller_takes_one_required_collaborator_and_one_read_face() -> None:
    """The durable store is the one *required* collaborator (it carries the
    connection, the fence and every statement). The second is the narrow
    Learning read face the §9 decision consumes — keyword-only and optional,
    because a world with no Learning wired still answers every durable face
    (and refuses only the recomputation, in this domain's words)."""

    parameters = inspect.signature(SchedulerController.__init__).parameters
    assert list(parameters) == ["self", "store", "learning"]
    learning = parameters["learning"]
    assert learning.kind is inspect.Parameter.KEYWORD_ONLY
    assert learning.default is None


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


def test_the_commands_protocol_declares_the_three_writes() -> None:
    """Two durable marks plus the §9 recomputation. The third is a *decision*
    (it computes a row before committing it), which is why it is declared on
    the command face and not implemented by the store."""

    declared = {
        name
        for name, member in vars(SchedulerCommands).items()
        if not name.startswith("_") and inspect.isfunction(member)
    }
    assert declared == {
        "recompute_schedule_item",
        "upsert_schedule_item",
        "record_review_event",
    }


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


@pytest.mark.parametrize("name", DUE_DECISION_FACES)
def test_the_due_decision_faces_declare_the_as_of_parameter(name: str) -> None:
    """The decision takes the instant it decides *at* as a parameter — never a
    clock — so ``as_of`` is the trailing argument of all three faces (P6-2's
    naming; the Phase 0 ``at`` spelling is gone with the reading it named)."""

    face = getattr(SchedulerController, name)
    parameters = list(inspect.signature(face).parameters)
    assert parameters[-1] == "as_of", name
    assert get_type_hints(face)["as_of"] is str


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
            "as_of",
        ] or parameters == [
            "target_type",
            "target_id",
            "evidence_modality",
            "as_of",
        ]


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
    made is kept by the shipped objects. The controller answers both faces,
    including the three-decisions wide command face. The store answers the two
    durable *marks* and the row reads but neither protocol whole — it has no
    ``get_schedule_view`` / ``is_review_due`` because a due decision is not a
    row read, and no ``recompute_schedule_item`` because a decision is not a
    row write: both belong to the face that holds the policy."""

    assert isinstance(scheduler_controller, SchedulerCommands)
    assert isinstance(scheduler_controller, SchedulerQueries)
    assert not isinstance(scheduler_store, SchedulerCommands)
    assert not isinstance(scheduler_store, SchedulerQueries)
    for name in ("upsert_schedule_item", "record_review_event"):
        assert hasattr(scheduler_store, name), name


def test_the_package_exports_are_complete() -> None:
    """A public module the ``__all__`` does not name is a face a consumer
    cannot find (the teaching review F10 lesson): every name the package
    surfaces is exported, exactly once, in sorted order. Since P6-2 that
    includes the spacing policy's declarations — what a row's version, window
    and urgency *mean* is exactly what a consumer reading a schedule row needs
    (the constants it was written from), plus the ports a caller wiring the
    controller must satisfy."""

    expected = {
        "FreshnessPort",
        "GRACE_DAYS",
        "INTERVAL_DAYS",
        "LearningReadPort",
        "REVIEW_EVENT_TABLE",
        "REVIEW_STATES",
        "ReviewEvent",
        "ReviewState",
        "SCHEDULER_MODEL_VERSION",
        "SCHEDULE_ITEM_TABLE",
        "SPACING_STAGES",
        "ScheduleItem",
        "ScheduleView",
        "SchedulerCommands",
        "SchedulerController",
        "SchedulerQueries",
        "SpacingStage",
        "SqliteSchedulerStore",
        "StaleSchedulerStoreError",
        "URGENCY_ANCHORS",
        "anchor_of",
        "next_window",
        "plan_schedule_item",
        "row_version",
        "schedule_item_id_for",
        "stage_from_history",
        "state_at",
        "urgency_of",
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
