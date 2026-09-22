"""P7-0 ①④ — the two User Configuration views.

``EffectiveSessionFocusView`` and ``PlannerConstraintView`` are consumer-side
shapes: neither adds a column, writes a row, or changes a face P6-0/P6-3
landed. What they freeze are the three readings §5.1 / §9 leave to a consumer
(the instant window, the half-declared target leg, the session binding), and
each freeze is pinned twice here: once behaviourally and once against the
module that states it.
"""

from __future__ import annotations

import ast
import sqlite3

from elc.platform.types import ConversationId, Err, Ok, TargetId
from elc.user_config.constraints import (
    applies_to,
    build_view,
    entries_for_target,
    entries_of_type,
    target_leg_of,
)
from elc.user_config.controller import UserConfigController
from elc.user_config.store import SqliteUserConfigStore
from elc.user_config.types import (
    PlannerConstraintScope,
    PlannerConstraintType,
    TargetLeg,
)

from .conftest import (
    CONSTRAINT_ID,
    CONV,
    DAY_ONE,
    DAY_ONE_PLUS,
    DAY_THREE,
    DAY_TWO,
    OFFSET_SPELLING,
    OTHER_CONV,
    OTHER_MODALITY,
    SAME_INSTANT_UTC,
    TARGET_ID,
    TARGET_TYPE,
    constraint,
    focus,
    source_text,
)

# -- the effective session focus ---------------------------------------------


def test_the_effective_focus_is_the_one_in_force_at_the_instant(
    conversations: tuple[ConversationId, ConversationId],
    user_config_store: SqliteUserConfigStore,
    user_config_controller: UserConfigController,
) -> None:
    assert isinstance(
        user_config_store.set_session_focus(
            focus("sf-old", starts_at=DAY_ONE, expires_at=DAY_ONE_PLUS)
        ),
        Ok,
    )
    assert isinstance(
        user_config_store.set_session_focus(
            focus("sf-current", starts_at=DAY_TWO, expires_at=DAY_THREE)
        ),
        Ok,
    )
    view = user_config_controller.get_effective_session_focus(
        CONV, DAY_TWO
    )
    assert isinstance(view, Ok) and view.value is not None
    assert view.value.session_focus_id == "sf-current"
    assert view.value.as_of == DAY_TWO
    assert view.value.base_goal_portfolio_version == "gv-1"


def test_the_window_boundaries_are_inclusive(
    conversations: tuple[ConversationId, ConversationId],
    user_config_store: SqliteUserConfigStore,
    user_config_controller: UserConfigController,
) -> None:
    assert isinstance(
        user_config_store.set_session_focus(
            focus("sf-window", starts_at=DAY_ONE, expires_at=DAY_THREE)
        ),
        Ok,
    )
    for instant in (DAY_ONE, DAY_TWO, DAY_THREE):
        view = user_config_controller.get_effective_session_focus(CONV, instant)
        assert isinstance(view, Ok) and view.value is not None, instant


def test_a_focus_outside_its_window_is_not_effective(
    conversations: tuple[ConversationId, ConversationId],
    user_config_store: SqliteUserConfigStore,
    user_config_controller: UserConfigController,
) -> None:
    assert isinstance(
        user_config_store.set_session_focus(
            focus("sf-window", starts_at=DAY_TWO, expires_at=DAY_THREE)
        ),
        Ok,
    )
    for instant in (DAY_ONE, "2026-09-24T09:00:01+00:00"):
        assert user_config_controller.get_effective_session_focus(
            CONV, instant
        ) == Ok(None)


def test_an_open_ended_focus_has_no_end(
    conversations: tuple[ConversationId, ConversationId],
    user_config_store: SqliteUserConfigStore,
    user_config_controller: UserConfigController,
) -> None:
    assert isinstance(
        user_config_store.set_session_focus(
            focus("sf-open", starts_at=DAY_ONE, expires_at=None)
        ),
        Ok,
    )
    view = user_config_controller.get_effective_session_focus(
        CONV, "2030-01-01T00:00:00+00:00"
    )
    assert isinstance(view, Ok) and view.value is not None
    assert view.value.expires_at is None


def test_no_focus_written_and_no_focus_in_force_are_both_none(
    conversations: tuple[ConversationId, ConversationId],
    user_config_controller: UserConfigController,
) -> None:
    assert user_config_controller.get_effective_session_focus(
        CONV, DAY_TWO
    ) == Ok(None)


def test_another_conversations_focus_is_not_this_conversations(
    conversations: tuple[ConversationId, ConversationId],
    user_config_store: SqliteUserConfigStore,
    user_config_controller: UserConfigController,
) -> None:
    assert isinstance(
        user_config_store.set_session_focus(
            focus("sf-elsewhere", conversation=OTHER_CONV)
        ),
        Ok,
    )
    assert user_config_controller.get_effective_session_focus(
        CONV, DAY_TWO
    ) == Ok(None)


def test_the_two_focus_reads_answer_their_own_question(
    conversations: tuple[ConversationId, ConversationId],
    user_config_store: SqliteUserConfigStore,
    user_config_controller: UserConfigController,
) -> None:
    """The byte-order read is **unchanged** and the two can disagree — which is
    exactly why the overlay is additive rather than a repair.

    Two focuses are written whose ``starts_at`` spellings sort one way as text
    and the other way as instants: ``17:00+08:00`` (09:00Z, the earlier
    instant) sorts *after* ``09:00+00:00`` as text. The byte-order read (P6-1,
    pinned in tests/phase6) picks the ``+08:00`` row as current; the
    instant-window read picks the row that is genuinely later in force at a
    later instant, and at an instant where only the earlier row's window is
    open it picks that one.
    """

    assert isinstance(
        user_config_store.set_session_focus(
            focus("sf-offset", starts_at=OFFSET_SPELLING, expires_at=DAY_THREE)
        ),
        Ok,
    )
    assert isinstance(
        user_config_store.set_session_focus(
            focus(
                "sf-utc",
                starts_at=SAME_INSTANT_UTC,
                expires_at="2026-09-22T10:00:00+00:00",
            )
        ),
        Ok,
    )
    byte_order = user_config_store.get_session_focus_for_conversation(CONV)
    assert isinstance(byte_order, Ok) and byte_order.value is not None
    assert byte_order.value.session_focus_id == "sf-offset"

    in_force = user_config_controller.get_effective_session_focus(
        CONV, "2026-09-22T10:30:00+00:00"
    )
    assert isinstance(in_force, Ok) and in_force.value is not None
    assert in_force.value.session_focus_id == "sf-offset"

    earlier_window = user_config_controller.get_effective_session_focus(
        CONV, "2026-09-22T09:30:00+00:00"
    )
    assert isinstance(earlier_window, Ok) and earlier_window.value is not None
    assert earlier_window.value.session_focus_id == "sf-utc"


def test_two_focuses_in_force_are_won_by_the_newest_started(
    conversations: tuple[ConversationId, ConversationId],
    user_config_store: SqliteUserConfigStore,
    user_config_controller: UserConfigController,
) -> None:
    assert isinstance(
        user_config_store.set_session_focus(
            focus("sf-first", starts_at=DAY_ONE, expires_at=DAY_THREE)
        ),
        Ok,
    )
    assert isinstance(
        user_config_store.set_session_focus(
            focus("sf-second", starts_at=DAY_TWO, expires_at=DAY_THREE)
        ),
        Ok,
    )
    view = user_config_controller.get_effective_session_focus(CONV, DAY_THREE)
    assert isinstance(view, Ok) and view.value is not None
    assert view.value.session_focus_id == "sf-second"


def test_an_unusable_start_instant_refuses_the_whole_read(
    conversations: tuple[ConversationId, ConversationId],
    user_config_store: SqliteUserConfigStore,
    user_config_controller: UserConfigController,
) -> None:
    assert isinstance(
        user_config_store.set_session_focus(
            focus("sf-good", starts_at=DAY_ONE, expires_at=DAY_THREE)
        ),
        Ok,
    )
    assert isinstance(
        user_config_store.set_session_focus(
            focus("sf-bad", starts_at="not-a-time", expires_at=None)
        ),
        Ok,
    )
    refusal = user_config_controller.get_effective_session_focus(CONV, DAY_TWO)
    assert isinstance(refusal, Err)
    assert "sf-bad" in refusal.error.message


def test_a_naive_or_empty_as_of_is_refused(
    conversations: tuple[ConversationId, ConversationId],
    user_config_controller: UserConfigController,
) -> None:
    for bad in ("", "2026-09-23T09:00:00", "not-a-time"):
        assert isinstance(
            user_config_controller.get_effective_session_focus(CONV, bad), Err
        ), bad


def test_a_closed_focus_with_an_unreadable_end_does_not_break_a_read_it_lost(
    conversations: tuple[ConversationId, ConversationId],
    user_config_store: SqliteUserConfigStore,
    user_config_controller: UserConfigController,
) -> None:
    """A row already excluded by ``starts_at > as_of`` never has its
    ``expires_at`` parsed — the same "a row the read has ruled out cannot break
    it" rule the constraint read declares."""

    assert isinstance(
        user_config_store.set_session_focus(
            focus("sf-later", starts_at=DAY_THREE, expires_at="not-a-time")
        ),
        Ok,
    )
    assert user_config_controller.get_effective_session_focus(
        CONV, DAY_TWO
    ) == Ok(None)


# -- the planner constraint view ---------------------------------------------


def test_the_view_carries_the_in_force_rows_normalized(
    user_config_store: SqliteUserConfigStore,
    user_config_controller: UserConfigController,
) -> None:
    assert isinstance(
        user_config_store.record_planner_constraint(constraint()), Ok
    )
    view = user_config_controller.get_planner_constraint_view(
        DAY_TWO, CONV
    )
    assert isinstance(view, Ok)
    assert view.value.as_of == DAY_TWO
    assert view.value.bound_conversation_id == CONV
    assert len(view.value.entries) == 1
    entry = view.value.entries[0]
    assert entry.constraint_id == CONSTRAINT_ID
    assert entry.constraint_type is PlannerConstraintType.DO_NOT_AUTO_TEACH
    assert entry.scope is PlannerConstraintScope.UNTIL_DATE
    assert entry.target_leg is TargetLeg.NOT_TARGET_LIMITED
    assert entry.starts_at == DAY_ONE
    assert entry.expires_at == DAY_THREE
    assert entry.active is True


def test_a_row_out_of_force_or_switched_off_is_not_in_the_view(
    user_config_store: SqliteUserConfigStore,
    user_config_controller: UserConfigController,
) -> None:
    assert isinstance(
        user_config_store.record_planner_constraint(
            constraint("pc-later", starts_at=DAY_THREE, expires_at=None)
        ),
        Ok,
    )
    assert isinstance(
        user_config_store.record_planner_constraint(
            constraint("pc-off", active=False, expires_at=None)
        ),
        Ok,
    )
    view = user_config_controller.get_planner_constraint_view(DAY_TWO, CONV)
    assert isinstance(view, Ok)
    assert view.value.entries == ()


def test_the_three_target_shapes_are_named(
    user_config_store: SqliteUserConfigStore,
) -> None:
    rows = (
        constraint("pc-general"),
        constraint("pc-target", target_type=TARGET_TYPE, target_id=TARGET_ID),
        constraint("pc-half-type", target_type=TARGET_TYPE),
        constraint("pc-half-id", target_id=TARGET_ID),
    )
    for row in rows:
        assert isinstance(user_config_store.record_planner_constraint(row), Ok)
    read = user_config_store.active_constraints(DAY_TWO)
    assert isinstance(read, Ok)
    legs = {row.constraint_id: target_leg_of(row) for row in read.value}
    assert legs == {
        "pc-general": TargetLeg.NOT_TARGET_LIMITED,
        "pc-half-id": TargetLeg.HALF_DECLARED,
        "pc-half-type": TargetLeg.HALF_DECLARED,
        "pc-target": TargetLeg.TARGET_LIMITED,
    }


def test_the_half_declared_leg_is_widened_and_marked(
    user_config_store: SqliteUserConfigStore,
    user_config_controller: UserConfigController,
) -> None:
    """The frozen reading (elc.user_config.constraints' rule 1): a half-declared
    target pair names no target to narrow to, so the prohibition is kept and
    applies to every target — and the widening is *visible* on the entry
    instead of silent."""

    for row in (
        constraint("pc-half-type", target_type=TARGET_TYPE),
        constraint("pc-half-id", target_id=TARGET_ID),
    ):
        assert isinstance(user_config_store.record_planner_constraint(row), Ok)
    view = user_config_controller.get_planner_constraint_view(DAY_TWO, CONV)
    assert isinstance(view, Ok)
    for entry in view.value.entries:
        assert entry.target_leg is TargetLeg.HALF_DECLARED
        assert applies_to(entry, TARGET_TYPE, TARGET_ID)
        assert applies_to(entry, "CAPABILITY", TargetId("cap-anything"))
    assert len(entries_for_target(view.value, TARGET_TYPE, TARGET_ID)) == 2


def test_a_target_limited_entry_matches_verbatim_only(
    user_config_store: SqliteUserConfigStore,
    user_config_controller: UserConfigController,
) -> None:
    assert isinstance(
        user_config_store.record_planner_constraint(
            constraint("pc-target", target_type=TARGET_TYPE, target_id=TARGET_ID)
        ),
        Ok,
    )
    view = user_config_controller.get_planner_constraint_view(DAY_TWO, CONV)
    assert isinstance(view, Ok)
    entry = view.value.entries[0]
    assert applies_to(entry, TARGET_TYPE, TARGET_ID)
    assert not applies_to(entry, "CAPABILITY", TARGET_ID)
    assert not applies_to(entry, TARGET_TYPE, TargetId("res-other"))


def test_the_store_target_read_still_excludes_the_half_declared_leg(
    user_config_store: SqliteUserConfigStore,
) -> None:
    """The P6-3 row read is **not** changed by this cut: it answers "which rows
    name this target verbatim", and a half-declared row names none. The view
    beside it answers the policy question (what does the user's constraint set
    forbid), which is why the two answer differently for exactly this shape —
    each docstring says which question it answers."""

    assert isinstance(
        user_config_store.record_planner_constraint(
            constraint("pc-half-type", target_type=TARGET_TYPE)
        ),
        Ok,
    )
    read = user_config_store.active_constraints_for_target(
        TARGET_TYPE, TARGET_ID, DAY_TWO
    )
    assert read == Ok(())
    assert user_config_store.active_constraints(DAY_TWO) != Ok(())


def test_the_types_filter_does_not_apply_anything(
    user_config_store: SqliteUserConfigStore,
    user_config_controller: UserConfigController,
) -> None:
    """``entries_of_type`` is a read: it selects rows and stops there (nothing
    in this repository acts on a ``DO_NOT_AUTO_TEACH`` row yet — the P6-3
    statement this cut does not change)."""

    assert isinstance(
        user_config_store.record_planner_constraint(
            constraint("pc-chat", constraint_type=PlannerConstraintType.JUST_CHAT)
        ),
        Ok,
    )
    assert isinstance(
        user_config_store.record_planner_constraint(constraint("pc-auto")), Ok
    )
    view = user_config_controller.get_planner_constraint_view(DAY_TWO, CONV)
    assert isinstance(view, Ok)
    assert [
        entry.constraint_id
        for entry in entries_of_type(
            view.value, PlannerConstraintType.JUST_CHAT
        )
    ] == ["pc-chat"]
    assert len(entries_of_type(view.value, PlannerConstraintType.MANUAL_FOCUS)) == 0


def test_this_session_is_bound_by_the_argument_and_adds_no_column(
    db: sqlite3.Connection,
    user_config_store: SqliteUserConfigStore,
    user_config_controller: UserConfigController,
) -> None:
    assert isinstance(
        user_config_store.record_planner_constraint(
            constraint("pc-session", scope=PlannerConstraintScope.THIS_SESSION)
        ),
        Ok,
    )
    first = user_config_controller.get_planner_constraint_view(DAY_TWO, CONV)
    second = user_config_controller.get_planner_constraint_view(
        DAY_TWO, OTHER_CONV
    )
    assert isinstance(first, Ok) and isinstance(second, Ok)
    assert first.value.bound_conversation_id == CONV
    assert second.value.bound_conversation_id == OTHER_CONV
    assert first.value.entries == second.value.entries

    columns = [
        str(row[1]) for row in db.execute("PRAGMA table_info(planner_constraint)")
    ]
    assert columns == [
        "constraint_id",
        "target_type",
        "target_id",
        "constraint_type",
        "scope",
        "starts_at",
        "expires_at",
        "created_from_turn_id",
        "active",
    ]
    assert "conversation_id" not in columns


def test_the_view_refuses_an_unusable_as_of(
    user_config_controller: UserConfigController,
) -> None:
    assert isinstance(
        user_config_controller.get_planner_constraint_view("", CONV), Err
    )


def test_build_view_is_pure_and_preserves_the_read_order() -> None:
    rows = (
        constraint("pc-b"),
        constraint("pc-a", constraint_type=PlannerConstraintType.JUST_CHAT),
    )
    view = build_view(rows, as_of=DAY_TWO, bound_conversation_id=CONV)
    assert [entry.constraint_id for entry in view.entries] == ["pc-b", "pc-a"]
    assert view.as_of == DAY_TWO
    assert view.bound_conversation_id == ConversationId("conv-p7-0")


def test_the_constraints_module_has_no_store_and_no_clock() -> None:
    """Structural half: the reading lives in a pure module, so its import set
    is the whole story — no sqlite3, no datetime, no other domain."""

    source = source_text("src/elc/user_config/constraints.py")
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert imported == {
        "__future__",
        "typing",
        "elc.platform.types",
        "elc.user_config.types",
    }
    for forbidden in ("SELECT", "INSERT", "UPDATE", "datetime", "sqlite3"):
        assert forbidden not in source, forbidden


def test_the_view_is_not_a_second_window_reading(
    user_config_store: SqliteUserConfigStore,
    user_config_controller: UserConfigController,
) -> None:
    """In-force membership is the store's reading, not the view's: a row the
    store excludes never reaches the view, and the view re-parses no stamp."""

    assert isinstance(
        user_config_store.record_planner_constraint(
            constraint("pc-early", starts_at="2026-01-01T00:00:00+00:00",
                       expires_at="2026-01-02T00:00:00+00:00")
        ),
        Ok,
    )
    view = user_config_controller.get_planner_constraint_view(DAY_TWO, CONV)
    assert isinstance(view, Ok)
    assert [entry.constraint_id for entry in view.value.entries] == []


def test_the_other_modality_leg_does_not_enter_a_constraint_read(
    user_config_store: SqliteUserConfigStore,
) -> None:
    """§9 has no modality column, so the target leg is the **pair** only — a
    constraint about one target applies to it whatever the evidence modality
    (the schedule key's modality leg is the Scheduler's, one object over)."""

    assert isinstance(
        user_config_store.record_planner_constraint(
            constraint("pc-target", target_type=TARGET_TYPE, target_id=TARGET_ID)
        ),
        Ok,
    )
    read = user_config_store.active_constraints_for_target(
        TARGET_TYPE, TARGET_ID, DAY_TWO
    )
    assert isinstance(read, Ok) and len(read.value) == 1
    assert OTHER_MODALITY.value not in read.value[0].constraint_id
