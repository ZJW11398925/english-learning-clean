"""P6-0 ④ — the authority face: the three graduated writes and their reads.

What the Phase 0 interfaces declare is what this file pins: the two write
faces whose result type is a version (``Result[GoalVersion]`` /
``Result[PolicyVersion]``) hand back the **durable** version — the same value
a later read returns — and the focus face hands back the durable focus. A
refusal travels through the controller unchanged (the store's ``CONFLICT``,
not a second vocabulary invented here), and the P4-3 faces are untouched:
the same four names, still no ``NotImplementedError``, still one collaborator
in the constructor.
"""

from __future__ import annotations

import inspect
import sqlite3

from elc.platform.types import ConversationId, Ok, PersonaId
from elc.user_config.controller import UserConfigController
from elc.user_config.types import (
    DisclosedUserProfile,
    DisclosureLevel,
    DisclosurePolicy,
    DisclosureRule,
    TeachingFrequency,
    UserProfile,
)
from tests.conftest import SRC_ROOT
from tests.phase3.sql_write_scan import write_targets

from .conftest import OTHER_USER, USER, goal, portfolio, session_focus, teaching_policy

P4_3_FACES = (
    "upsert_user_profile",
    "set_disclosure_policy",
    "get_user_profile",
    "get_disclosed_user_profile",
)
P6_0_FACES = (
    "upsert_goal_portfolio",
    "upsert_teaching_policy",
    "set_session_focus",
    "get_goal_portfolio",
    "get_teaching_policy",
    "get_session_focus",
)


def test_the_p6_0_faces_are_real_and_the_p4_3_faces_are_untouched() -> None:
    """The graduation is source-level: none of the six P6-0 faces raises a
    phase pointer any more, the four P4-3 faces still do not raise, and the
    controller still takes exactly one collaborator (the store) — no
    learning, teaching or persona port was added to reach these rows."""

    for name in P6_0_FACES + P4_3_FACES:
        source = inspect.getsource(getattr(UserConfigController, name))
        assert "NotImplementedError" not in source, name
    parameters = inspect.signature(UserConfigController.__init__).parameters
    assert list(parameters) == ["self", "store"]
    assert write_targets(SRC_ROOT / "user_config" / "controller.py") == set()


def test_the_portfolio_face_returns_the_durable_version(
    user_config_controller: UserConfigController,
) -> None:
    written = user_config_controller.upsert_goal_portfolio(
        portfolio(goal("g-1"))
    )
    assert isinstance(written, Ok), written
    read = user_config_controller.get_goal_portfolio(USER)
    assert isinstance(read, Ok) and read.value is not None
    assert written.value == read.value.goal_version == "gv-1"
    # The durable row is the only source of that version: a second read (and
    # a second write of the same content) says the same thing.
    replay = user_config_controller.upsert_goal_portfolio(portfolio(goal("g-1")))
    assert isinstance(replay, Ok) and replay.value == written.value


def test_the_policy_face_returns_the_durable_version(
    user_config_controller: UserConfigController,
) -> None:
    written = user_config_controller.upsert_teaching_policy(
        teaching_policy(frequency=TeachingFrequency.EAGER)
    )
    assert isinstance(written, Ok), written
    read = user_config_controller.get_teaching_policy(USER)
    assert isinstance(read, Ok) and read.value is not None
    assert written.value == read.value.policy_version == "pv-1"
    assert read.value.teaching_frequency is TeachingFrequency.EAGER


def test_a_refusal_travels_through_the_controller_unchanged(
    user_config_controller: UserConfigController,
) -> None:
    assert isinstance(
        user_config_controller.upsert_teaching_policy(teaching_policy()), Ok
    )
    refused = user_config_controller.upsert_teaching_policy(
        teaching_policy(mode="SOCRATIC")
    )
    assert not isinstance(refused, Ok)
    assert refused.error.code.value == "CONFLICT"
    # ... and the durable row is exactly what it was.
    read = user_config_controller.get_teaching_policy(USER)
    assert isinstance(read, Ok) and read.value is not None
    assert read.value.mode is None


def test_the_focus_face_returns_the_durable_focus(
    user_config_controller: UserConfigController, conversation
) -> None:
    del conversation
    written = user_config_controller.set_session_focus(
        session_focus("sf-1", target="res-hedge-i-think")
    )
    assert isinstance(written, Ok), written
    read = user_config_controller.get_session_focus("sf-1")
    assert isinstance(read, Ok) and read.value is not None
    assert read.value == written.value
    assert str(read.value.manual_focus_target) == "res-hedge-i-think"


def test_the_three_reads_delegate_and_answer_none_before_any_write(
    user_config_controller: UserConfigController,
) -> None:
    assert user_config_controller.get_goal_portfolio(USER).value is None
    assert user_config_controller.get_teaching_policy(USER).value is None
    assert user_config_controller.get_session_focus("sf-1").value is None
    assert user_config_controller.get_goal_portfolio(OTHER_USER).value is None


def test_the_p4_3_faces_still_work_over_the_same_store(
    db: sqlite3.Connection,
    user_config_controller: UserConfigController,
) -> None:
    """P6-0 added rows, not behavior: the profile/disclosure faces answer the
    same way with the three new tables present and populated."""

    assert isinstance(
        user_config_controller.upsert_user_profile(
            UserProfile(
                user_profile_id=USER,
                revision="rev-1",
                preferences=("short replies",),
            ),
            explicit_consent=True,
        ),
        Ok,
    )
    assert isinstance(
        user_config_controller.set_disclosure_policy(
            DisclosurePolicy(
                disclosure_policy_id=str(USER),
                revision="pol-1",
                rules=(
                    DisclosureRule(
                        persona_id=None,
                        disclosure_level=DisclosureLevel.FUNCTIONAL,
                    ),
                ),
            )
        ),
        Ok,
    )
    assert isinstance(
        user_config_controller.upsert_goal_portfolio(portfolio(goal("g-1"))), Ok
    )
    disclosed = user_config_controller.get_disclosed_user_profile(
        USER, PersonaId("persona-a")
    )
    assert isinstance(disclosed, Ok)
    assert isinstance(disclosed.value, DisclosedUserProfile)
    assert disclosed.value.disclosed_facts == ("short replies",)
    assert db.execute("SELECT COUNT(*) FROM goal_portfolio").fetchone() == (1,)


def test_a_focus_read_is_keyed_by_its_own_id_not_by_user(
    user_config_controller: UserConfigController, conversation
) -> None:
    """The query protocol spells the parameter ``session_focus_id`` (§5.1's
    object has no user leg), and the face behaves that way: the user id is
    not a key that finds a focus."""

    del conversation
    assert isinstance(
        user_config_controller.set_session_focus(session_focus("sf-1")), Ok
    )
    assert user_config_controller.get_session_focus(str(USER)).value is None
    found = user_config_controller.get_session_focus("sf-1")
    assert isinstance(found, Ok) and found.value is not None
    assert found.value.session_focus_id == "sf-1"
    assert found.value.conversation_id == ConversationId("conv-p6-0")
