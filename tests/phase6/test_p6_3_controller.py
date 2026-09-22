"""P6-3 ③.4 — the five faces through the authority face.

The controller owns no rule of its own (the P6-0/P6-1 layering), so what is
pinned here is: the two protocols declare the five faces, the controller
implements every one of them, each call reaches the store and comes back
unchanged (including the refusals — a ``CONFLICT`` / ``NOT_FOUND`` /
``VALIDATION_FAILED`` the store produces is the code the caller gets), and the
controller itself carries no SQL and imports no database handle.
"""

from __future__ import annotations

import dataclasses
import inspect
import sqlite3

import pytest

from elc.platform.types import DomainErrorCode, Err, Ok, TargetId
from elc.user_config import (
    PlannerConstraint,
    PlannerConstraintScope,
    PlannerConstraintType,
    UserConfigCommands,
    UserConfigController,
    UserConfigQueries,
)
from elc.user_config.store import SqliteUserConfigStore
from elc.user_config.types import PlannerConstraint as TypesModuleConstraint
from tests.conftest import SRC_ROOT
from tests.phase3.sql_write_scan import write_targets

from .conftest import (
    AS_OF,
    CONSTRAINT_ID,
    CONSTRAINT_START,
    OTHER_USER,
    TARGET_ID,
    TARGET_TYPE,
    planner_constraint,
)

CONTROLLER_PATH = SRC_ROOT / "user_config" / "controller.py"


@pytest.fixture()
def controller(user_config_store: SqliteUserConfigStore) -> UserConfigController:
    return UserConfigController(user_config_store)


# -- ① the protocols ---------------------------------------------------------


def test_the_command_protocol_declares_the_two_writes() -> None:
    declared = {
        name
        for name, member in vars(UserConfigCommands).items()
        if inspect.isfunction(member) and not name.startswith("_")
    }
    assert {
        "record_planner_constraint",
        "set_planner_constraint_active",
    } <= declared


def test_the_query_protocol_declares_the_three_reads() -> None:
    declared = {
        name
        for name, member in vars(UserConfigQueries).items()
        if inspect.isfunction(member) and not name.startswith("_")
    }
    assert {
        "get_planner_constraint",
        "active_constraints",
        "active_constraints_for_target",
    } <= declared


def test_the_command_protocol_is_satisfied_structurally() -> None:
    """Every write the command protocol declares is implemented, so the
    runtime-checkable face holds."""

    controller = UserConfigController.__new__(UserConfigController)
    assert isinstance(controller, UserConfigCommands)


def test_the_query_faces_are_implemented_without_the_policy_read() -> None:
    """The authority face does **not** structurally satisfy
    ``UserConfigQueries``, and that is P4-3's design rather than a gap: the
    protocol declares ``get_disclosure_policy``, which this face has never
    exposed — the policy is read only *inside*
    ``get_disclosed_user_profile``, so the full policy never leaves the face
    (§5.1 Rules). The five P6-3 faces are implemented all the same; the
    completeness pin for them is the face-list test below."""

    controller = UserConfigController.__new__(UserConfigController)
    assert not hasattr(controller, "get_disclosure_policy")
    for face in (
        "get_planner_constraint",
        "active_constraints",
        "active_constraints_for_target",
    ):
        assert hasattr(UserConfigQueries, face), face
        assert callable(getattr(controller, face)), face
        assert inspect.signature(
            getattr(UserConfigQueries, face)
        ) == inspect.signature(getattr(UserConfigController, face)), face


def test_the_controller_implements_every_declared_face(
    controller: UserConfigController,
) -> None:
    """The five new faces plus the eleven the earlier cuts landed — no face a
    protocol declares is missing, and none was renamed away. P7-0's two
    consumer views are additive (no earlier face changed shape)."""

    declared = {
        name
        for name, member in inspect.getmembers(
            UserConfigController, inspect.isfunction
        )
        if not name.startswith("_")
    }
    assert declared == {
        # P4-3 / P6-0 / P6-1
        "upsert_user_profile",
        "set_disclosure_policy",
        "get_user_profile",
        "get_disclosed_user_profile",
        "upsert_goal_portfolio",
        "upsert_teaching_policy",
        "set_session_focus",
        "get_goal_portfolio",
        "get_teaching_policy",
        "get_session_focus",
        "get_session_focus_for_conversation",
        # P6-3
        "record_planner_constraint",
        "set_planner_constraint_active",
        "get_planner_constraint",
        "active_constraints",
        "active_constraints_for_target",
        # P7-0
        "get_effective_session_focus",
        "get_planner_constraint_view",
    }


# -- ② the write faces -------------------------------------------------------


def test_the_record_face_returns_the_durable_row(
    db: sqlite3.Connection, controller: UserConfigController
) -> None:
    written = planner_constraint(
        target_type=TARGET_TYPE, target_id=TARGET_ID
    )
    result = controller.record_planner_constraint(written)
    assert isinstance(result, Ok), result
    assert result.value == written
    assert db.execute(
        "SELECT constraint_id, target_type, active FROM planner_constraint"
    ).fetchall() == [(CONSTRAINT_ID, TARGET_TYPE, 1)]


def test_the_record_face_refuses_a_differing_replay(
    controller: UserConfigController,
) -> None:
    written = planner_constraint()
    assert isinstance(controller.record_planner_constraint(written), Ok)
    refused = controller.record_planner_constraint(
        dataclasses.replace(written, scope=PlannerConstraintScope.THIS_SESSION)
    )
    assert isinstance(refused, Err), refused
    assert refused.error.code is DomainErrorCode.CONFLICT


def test_the_record_face_carries_the_stores_not_found(
    controller: UserConfigController,
) -> None:
    refused = controller.record_planner_constraint(
        planner_constraint(created_from_turn="t-absent")
    )
    assert isinstance(refused, Err), refused
    assert refused.error.code is DomainErrorCode.NOT_FOUND


def test_the_record_face_carries_the_stores_validation_failure(
    controller: UserConfigController,
) -> None:
    refused = controller.record_planner_constraint(
        planner_constraint(target_type="GOAL", target_id=TARGET_ID)
    )
    assert isinstance(refused, Err), refused
    assert refused.error.code is DomainErrorCode.VALIDATION_FAILED


def test_the_transfer_face_moves_the_flag(
    db: sqlite3.Connection, controller: UserConfigController
) -> None:
    assert isinstance(
        controller.record_planner_constraint(planner_constraint()), Ok
    )
    moved = controller.set_planner_constraint_active(CONSTRAINT_ID, False)
    assert isinstance(moved, Ok), moved
    assert moved.value.active is False
    assert db.execute(
        "SELECT active FROM planner_constraint WHERE constraint_id = ?",
        (CONSTRAINT_ID,),
    ).fetchone() == (0,)


def test_the_transfer_face_carries_the_stores_not_found(
    controller: UserConfigController,
) -> None:
    refused = controller.set_planner_constraint_active("pc-absent", True)
    assert isinstance(refused, Err), refused
    assert refused.error.code is DomainErrorCode.NOT_FOUND


# -- ③ the read faces --------------------------------------------------------


def test_the_identity_read_reaches_the_store(
    controller: UserConfigController,
) -> None:
    written = planner_constraint()
    assert isinstance(controller.record_planner_constraint(written), Ok)
    assert controller.get_planner_constraint(CONSTRAINT_ID) == Ok(written)
    assert controller.get_planner_constraint("pc-absent") == Ok(None)


def test_the_general_read_reaches_the_store(
    controller: UserConfigController,
) -> None:
    assert isinstance(
        controller.record_planner_constraint(planner_constraint()), Ok
    )
    result = controller.active_constraints(AS_OF)
    assert isinstance(result, Ok), result
    assert [constraint.constraint_id for constraint in result.value] == [
        CONSTRAINT_ID
    ]


def test_the_target_read_reaches_the_store(
    controller: UserConfigController,
) -> None:
    specific = planner_constraint(
        "pc-specific", target_type=TARGET_TYPE, target_id=TARGET_ID
    )
    assert isinstance(controller.record_planner_constraint(specific), Ok)
    matching = controller.active_constraints_for_target(
        TARGET_TYPE, TARGET_ID, AS_OF
    )
    assert isinstance(matching, Ok), matching
    assert [constraint.constraint_id for constraint in matching.value] == [
        "pc-specific"
    ]
    other = controller.active_constraints_for_target(
        TARGET_TYPE, TargetId("res-other"), AS_OF
    )
    assert other == Ok(())


def test_the_reads_carry_the_stores_validation_failure(
    controller: UserConfigController,
) -> None:
    for read in (
        lambda: controller.active_constraints(""),
        lambda: controller.active_constraints_for_target(
            TARGET_TYPE, TARGET_ID, "yesterday"
        ),
    ):
        refused = read()
        assert isinstance(refused, Err), refused
        assert refused.error.code is DomainErrorCode.VALIDATION_FAILED


def test_the_reads_do_not_write(
    db: sqlite3.Connection, controller: UserConfigController
) -> None:
    assert isinstance(
        controller.record_planner_constraint(planner_constraint()), Ok
    )
    before = db.total_changes
    controller.get_planner_constraint(CONSTRAINT_ID)
    controller.active_constraints(AS_OF)
    controller.active_constraints_for_target(TARGET_TYPE, TARGET_ID, AS_OF)
    assert db.total_changes == before


def test_a_full_round_trip_through_the_controller(
    controller: UserConfigController,
) -> None:
    """Enter a constraint, read it, clear it, read again, re-enable, read
    again: the four faces answer consistently at every step."""

    written = planner_constraint(
        scope=PlannerConstraintScope.UNTIL_USER_REENABLES, expires_at=None
    )
    assert isinstance(controller.record_planner_constraint(written), Ok)
    assert controller.get_planner_constraint(CONSTRAINT_ID) == Ok(written)
    assert len(controller.active_constraints(AS_OF).value) == 1
    assert isinstance(
        controller.set_planner_constraint_active(CONSTRAINT_ID, False), Ok
    )
    assert controller.active_constraints(AS_OF) == Ok(())
    assert isinstance(
        controller.set_planner_constraint_active(CONSTRAINT_ID, True), Ok
    )
    assert len(controller.active_constraints(AS_OF).value) == 1


# -- ④ the controller's own reach --------------------------------------------


def test_the_controller_carries_no_sql() -> None:
    """Pure delegation, structurally: the AST scan finds no write statement in
    the controller (the store is the only writer)."""

    assert write_targets(CONTROLLER_PATH) == set()


def test_the_controller_imports_no_database_handle() -> None:
    source = CONTROLLER_PATH.read_text(encoding="utf-8")
    assert "import sqlite3" not in source
    assert ".execute(" not in source
    assert "connect(" not in source


def test_the_other_faces_are_untouched_by_a_constraint_write(
    db: sqlite3.Connection, controller: UserConfigController
) -> None:
    """A constraint is not a goal, a policy or a focus: writing one leaves the
    five earlier configuration tables empty, and their reads still answer
    ``None``."""

    assert isinstance(
        controller.record_planner_constraint(planner_constraint()), Ok
    )
    for table in (
        "user_profile",
        "disclosure_policy",
        "goal_portfolio",
        "teaching_policy",
        "session_focus",
    ):
        assert db.execute(f"SELECT COUNT(*) FROM {table}").fetchone() == (0,)
    for read in (
        controller.get_goal_portfolio(OTHER_USER),
        controller.get_teaching_policy(OTHER_USER),
        controller.get_session_focus("sf-absent"),
        controller.get_user_profile(OTHER_USER),
    ):
        assert read == Ok(None)


def test_the_package_exposes_the_object_and_the_two_enums() -> None:
    """A face a consumer cannot find is a face it re-implements: the package
    exports the object, both enums and both word lists."""

    import elc.user_config as package

    assert package.PlannerConstraint is TypesModuleConstraint
    assert package.PlannerConstraintType is PlannerConstraintType
    assert package.PlannerConstraintScope is PlannerConstraintScope
    assert package.PLANNER_CONSTRAINT_TYPES == tuple(
        member.value for member in PlannerConstraintType
    )
    assert package.PLANNER_CONSTRAINT_SCOPES == tuple(
        member.value for member in PlannerConstraintScope
    )
    for name in (
        "PlannerConstraint",
        "PlannerConstraintScope",
        "PlannerConstraintType",
    ):
        assert name in package.__all__, name


def test_the_object_is_the_one_the_package_and_the_store_share() -> None:
    """One class, not two spellings of it: the store's decode and the caller's
    construction are the same type."""

    assert PlannerConstraint is TypesModuleConstraint
    instance = PlannerConstraint(
        constraint_id="pc-1",
        constraint_type=PlannerConstraintType.JUST_CHAT,
        scope=PlannerConstraintScope.THIS_SESSION,
        starts_at=CONSTRAINT_START,
        active=True,
    )
    assert isinstance(instance, PlannerConstraint)
