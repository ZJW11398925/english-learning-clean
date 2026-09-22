"""P7-2 ③④ — §12's ``UserIntentScope`` and §13's ``ConversationPriorityView``.

The vocabulary pins are extractions: the six scope words come out of
``docs/DOMAIN_MODEL.md`` §12 and the two §13 blocks out of §13, so a
transcription slip fails a test instead of shipping. The behaviour pins are
read through the real §9 faces (an in-memory app.db, an opened epoch, the real
User Configuration controller) wherever a row can carry the fact, and through
this cut's declared shapes only where no producer exists (the two scope words
the module registers as unproduced).
"""

from __future__ import annotations

import sqlite3

import pytest

from elc.planner.scope import (
    FLOW_PRIORITY_WORDS,
    FLOW_TO_INTERRUPTION_COST_BAND,
    INTERACTION_PHASE_WORDS,
    REACHABLE_SCOPE_WORDS,
    UNPRODUCED_SCOPE_WORDS,
    ConversationPriorityView,
    FlowPriority,
    InteractionPhase,
    interruption_cost_band_of,
    resolve_user_intent_scope,
)
from elc.planner.types import UserIntentScope
from elc.platform.db import epoch
from elc.platform.types import Ok
from elc.user_config.controller import UserConfigController
from elc.user_config.store import SqliteUserConfigStore
from elc.user_config.types import (
    PlannerConstraintScope,
    PlannerConstraintType,
)

from .conftest import (
    CONV,
    DAY_ONE,
    DAY_THREE,
    DAY_TWO,
    TARGET_ID,
    canonical_lines,
    constraint,
    document_text,
)


def _scope_block(doc: str, heading: str) -> tuple[str, ...]:
    return canonical_lines(doc, heading)


# -- ③ §12, word for word ----------------------------------------------------


def test_the_six_scope_words_are_the_canonical_block() -> None:
    """docs/DOMAIN_MODEL.md §12's fenced block, in its own order."""

    assert _scope_block("DOMAIN_MODEL.md", "## 12. UserIntentScope") == (
        "OPEN",
        "LEARNING_REQUEST",
        "TARGETED_LEARNING_REQUEST",
        "JUST_CHAT",
        "NON_LEARNING_TASK",
        "ACTIVE_TEACHING_CONTINUATION",
    )
    assert tuple(str(word) for word in UserIntentScope) == (
        "OPEN",
        "LEARNING_REQUEST",
        "TARGETED_LEARNING_REQUEST",
        "JUST_CHAT",
        "NON_LEARNING_TASK",
        "ACTIVE_TEACHING_CONTINUATION",
    )


def test_the_module_quotes_the_scope_constraint_sentence() -> None:
    """"`TARGETED_LEARNING_REQUEST` 是 candidate-scope constraint，不是普通
    bonus" — the sentence that makes the word a filter rather than a boost, and
    the module says so where the word is resolved."""

    lines = document_text("DOMAIN_MODEL.md")
    assert any(
        "TARGETED_LEARNING_REQUEST" in line and "candidate-scope constraint" in line
        for line in lines
    )
    from elc.planner import scope

    # A module docstring is line-wrapped; the quote is compared as text.
    prose = " ".join((scope.__doc__ or "").split())
    assert "a candidate-scope constraint, not an ordinary bonus" in prose


# -- ④ §13, word for word ----------------------------------------------------


def test_the_flow_priority_and_phase_blocks_are_the_canonical_ones() -> None:
    """§13's two blocks, verbatim, and the three fields of the view."""

    blocks = canonical_lines("DOMAIN_MODEL.md", "## 13. ConversationPriorityView")
    # The section's one fenced block carries all three fields: flow_priority
    # and its four words, interaction_phase and its seven, then the boolean.
    assert "flow_priority:" in blocks
    assert "interaction_phase:" in blocks
    assert blocks[-1] == "natural_break_available"

    assert tuple(FLOW_PRIORITY_WORDS) == ("LOW", "NORMAL", "HIGH", "PROTECTED")
    assert tuple(str(word) for word in FlowPriority) == tuple(FLOW_PRIORITY_WORDS)
    assert INTERACTION_PHASE_WORDS == (
        "OPEN",
        "DEEP_EXCHANGE",
        "TASK_EXECUTION",
        "STORY_FLOW",
        "USER_SUPPORT",
        "TEACHING",
        "WRAP_UP",
    )
    assert tuple(str(word) for word in InteractionPhase) == (
        INTERACTION_PHASE_WORDS
    )

    view = ConversationPriorityView(
        flow_priority=FlowPriority.NORMAL,
        interaction_phase=InteractionPhase.OPEN,
        natural_break_available=False,
    )
    assert tuple(field for field in vars(view)) == (
        "flow_priority",
        "interaction_phase",
        "natural_break_available",
    )


def test_the_view_authorises_nothing_and_the_gate_keeps_that_authority() -> None:
    """§13's closing line — the Gate keeps the authorization authority — is
    quoted, and the only thing this module derives from the view is a *cost*
    band (BF-02 §17: ``interruption_cost = PROTECTED`` is a cost, never an
    exclusion)."""

    lines = document_text("DOMAIN_MODEL.md")
    assert any("Gate 保留最终授权权威" in line for line in lines)
    from elc.planner import scope

    assert "Gate 保留最终授权权威" in (scope.__doc__ or "")
    assert "never an exclusion" in (scope.__doc__ or "")


def test_the_interruption_cost_band_is_the_shared_word_one_ladder_over() -> None:
    """The declared reading, pinned: identity on the four words, ``None`` when
    there is no view, and every band a real band of BF-02 §6's
    ``interruption_cost`` ladder."""

    for priority, band in FLOW_TO_INTERRUPTION_COST_BAND.items():
        assert band == str(priority)
        assert (
            interruption_cost_band_of(
                ConversationPriorityView(
                    flow_priority=priority,
                    interaction_phase=InteractionPhase.OPEN,
                    natural_break_available=False,
                )
            )
            == band
        )
    assert interruption_cost_band_of(None) is None
    from elc.planner.candidates import FACTOR_BAND_VALUES

    assert set(FLOW_TO_INTERRUPTION_COST_BAND.values()) <= set(
        FACTOR_BAND_VALUES["interruption_cost"]
    )


# -- ③ the resolution --------------------------------------------------------


def test_no_view_is_open_and_says_the_authority_is_missing() -> None:
    """``OPEN`` is §12's word for "nothing is declared" — and the resolution
    carries the fact that no view was read, so a caller can register P7-0's
    ``constraint_view_present`` leg separately."""

    resolution = resolve_user_intent_scope(None)
    assert resolution.scope is UserIntentScope.OPEN
    assert resolution.constraint_view_present is False
    assert resolution.request_targets == ()
    assert "no §9 PlannerConstraintView" in resolution.reasons[0]


def test_an_empty_view_is_open_with_the_view_present() -> None:
    from elc.user_config.constraints import build_view

    empty = build_view((), as_of=DAY_TWO, bound_conversation_id=CONV)
    resolution = resolve_user_intent_scope(empty)
    assert resolution.scope is UserIntentScope.OPEN
    assert resolution.constraint_view_present is True
    assert "no entry that bears on the scope" in resolution.reasons[0]


@pytest.mark.parametrize(
    ("constraint_type", "expected"),
    [
        pytest.param(
            PlannerConstraintType.JUST_CHAT, "JUST_CHAT", id="just-chat"
        ),
        pytest.param(
            PlannerConstraintType.MANUAL_FOCUS,
            "LEARNING_REQUEST",
            id="general-focus",
        ),
        pytest.param(
            PlannerConstraintType.DO_NOT_AUTO_TEACH, "OPEN", id="auto-off"
        ),
        pytest.param(
            PlannerConstraintType.SUPPRESS_REVIEW, "OPEN", id="no-review"
        ),
    ],
)
def test_the_scope_word_follows_the_users_own_rows(
    constraint_type: PlannerConstraintType, expected: str
) -> None:
    """One §9 row at a time, through the real view builder: only the
    MANUAL_FOCUS and JUST_CHAT words bear on the scope, and a
    MANUAL_FOCUS with no target is the general request rather than a scope
    constraint."""

    row = constraint(
        constraint_type=constraint_type,
        scope=PlannerConstraintScope.UNTIL_USER_REENABLES,
        target_type=None,
        target_id=None,
    )
    from elc.user_config.constraints import build_view

    resolution = resolve_user_intent_scope(
        build_view((row,), as_of=DAY_TWO, bound_conversation_id=CONV)
    )
    assert resolution.scope.value == expected


def test_a_targeted_manual_focus_is_the_scope_constraint() -> None:
    """A MANUAL_FOCUS naming a target is §12's TARGETED_LEARNING_REQUEST, and
    the target travels with the resolution so the generator can serve it."""

    from elc.user_config.constraints import build_view

    row = constraint(
        constraint_type=PlannerConstraintType.MANUAL_FOCUS,
        scope=PlannerConstraintScope.THIS_SESSION,
        target_type="RESOURCE",
        target_id=TARGET_ID,
    )
    resolution = resolve_user_intent_scope(
        build_view((row,), as_of=DAY_TWO, bound_conversation_id=CONV)
    )
    assert resolution.scope is UserIntentScope.TARGETED_LEARNING_REQUEST
    assert len(resolution.request_targets) == 1
    requested = resolution.request_targets[0]
    assert requested.constraint_id == row.constraint_id
    assert requested.target_type == "RESOURCE"
    assert requested.target_id == TARGET_ID
    assert "candidate-scope word" in resolution.reasons[0]


def test_an_explicit_request_outranks_a_just_chat_switch() -> None:
    """BF-02 §9's remedy sentence, as precedence: the scope word changes to the
    request scope first, which is why the kernel never sees the
    JUST_CHAT + user-initiated pair it refuses."""

    from elc.user_config.constraints import build_view

    view = build_view(
        (
            constraint(
                constraint_id="pc-just-chat",
                constraint_type=PlannerConstraintType.JUST_CHAT,
                scope=PlannerConstraintScope.UNTIL_USER_REENABLES,
                target_type=None,
                target_id=None,
            ),
            constraint(
                constraint_id="pc-manual",
                constraint_type=PlannerConstraintType.MANUAL_FOCUS,
                scope=PlannerConstraintScope.THIS_SESSION,
                target_type="RESOURCE",
                target_id=TARGET_ID,
            ),
        ),
        as_of=DAY_TWO,
        bound_conversation_id=CONV,
    )
    resolution = resolve_user_intent_scope(view)
    assert resolution.scope is UserIntentScope.TARGETED_LEARNING_REQUEST
    assert "BF-02 §9's remedy sentence" in resolution.reasons[0]


def test_the_reachable_and_unproduced_words_partition_the_vocabulary() -> None:
    """Six words, four reachable from a landed read face, two registered as
    unproduced — and the two are exactly the words whose authorities the module
    names (RA §4 step 3's turn reading; the Gate's open-moment state)."""

    assert set(REACHABLE_SCOPE_WORDS) | set(UNPRODUCED_SCOPE_WORDS) == {
        str(word) for word in UserIntentScope
    }
    assert not set(REACHABLE_SCOPE_WORDS) & set(UNPRODUCED_SCOPE_WORDS)
    assert set(UNPRODUCED_SCOPE_WORDS) == {
        "NON_LEARNING_TASK",
        "ACTIVE_TEACHING_CONTINUATION",
    }
    from elc.planner import scope

    assert "NON_LEARNING_TASK" in (scope.__doc__ or "")
    assert "ACTIVE_TEACHING_CONTINUATION" in (scope.__doc__ or "")


def test_the_real_rows_are_what_the_resolver_reads(
    conversations: tuple[object, object],
    user_config_store: SqliteUserConfigStore,
    user_config_controller: UserConfigController,
) -> None:
    """The real chain: a real §9 row written through the store, read back
    through P6-3's view at an instant inside its window, and resolved.

    The window matters — the read the resolver consumes is ``active_constraints``
    (in force at ``as_of``), so a row outside its window answers nothing, which
    is the same fact one instant either side."""

    assert isinstance(
        user_config_store.record_planner_constraint(
            constraint(
                constraint_id="pc-scope-real",
                constraint_type=PlannerConstraintType.MANUAL_FOCUS,
                scope=PlannerConstraintScope.UNTIL_DATE,
                target_type="RESOURCE",
                target_id=TARGET_ID,
                starts_at=DAY_ONE,
                expires_at=DAY_THREE,
            )
        ),
        Ok,
    )

    inside = user_config_controller.get_planner_constraint_view(DAY_TWO, CONV)
    assert isinstance(inside, Ok)
    resolution = resolve_user_intent_scope(inside.value)
    assert resolution.scope is UserIntentScope.TARGETED_LEARNING_REQUEST
    assert resolution.request_targets[0].target_id == TARGET_ID

    # the same world, one instant past the window: nothing in force.
    outside = user_config_controller.get_planner_constraint_view(
        "2026-09-25T09:00:00+00:00", CONV
    )
    assert isinstance(outside, Ok)
    assert resolve_user_intent_scope(outside.value).scope is UserIntentScope.OPEN
    assert outside.value.entries == ()


def test_the_resolver_reads_no_clock_and_no_random_source() -> None:
    """Determinism, stated structurally: the resolver's module uses no clock,
    no randomness and no store (the view it reads is a record)."""

    from elc.planner import scope as scope_module

    text = (
        __import__("pathlib").Path(scope_module.__file__).read_text(
            encoding="utf-8"
        )
    )
    for forbidden in (
        "import time",
        "time.time",
        "import random",
        "datetime.now",
        "sqlite3",
        ".store",
    ):
        assert forbidden not in text, forbidden


def test_the_half_declared_leg_is_widened_by_p6_3_and_not_here() -> None:
    """P6-3's rule 1 (a half-declared target leg applies to every target) is
    consumed rather than re-decided: a row with a target_id and no target_type
    still becomes a requested target, carried verbatim."""

    from elc.user_config.constraints import build_view

    row = constraint(
        constraint_type=PlannerConstraintType.MANUAL_FOCUS,
        scope=PlannerConstraintScope.THIS_SESSION,
        target_type=None,
        target_id=TARGET_ID,
    )
    resolution = resolve_user_intent_scope(
        build_view((row,), as_of=DAY_TWO, bound_conversation_id=CONV)
    )
    assert resolution.scope is UserIntentScope.TARGETED_LEARNING_REQUEST
    requested = resolution.request_targets[0]
    assert requested.target_type is None
    assert requested.target_id == TARGET_ID


def test_a_fresh_database_has_no_scope_rows_and_the_resolver_is_open(
    db: sqlite3.Connection,
) -> None:
    """The world the suite starts from: no constraint rows at all, so the scope
    is OPEN with the view present — the two "nothing declared" cases
    (no view / no entry) are distinguishable and both are pinned."""

    opened = epoch.open_runtime_epoch(db)
    controller = UserConfigController(SqliteUserConfigStore(db, opened))
    view = controller.get_planner_constraint_view(DAY_TWO, CONV)
    assert isinstance(view, Ok)
    assert view.value.entries == ()
    resolution = resolve_user_intent_scope(view.value)
    assert resolution.scope is UserIntentScope.OPEN
    assert resolution.constraint_view_present is True


def test_the_view_is_the_three_fields_and_only_the_priority_is_read() -> None:
    """§13's three fields, no fourth, and one declared reading: the *precedence*
    decides the cost band — the phase and the break availability do not (the
    break availability is BF-02 §5's context field and §13's safeguard input,
    not a cost input)."""

    import dataclasses

    fields = tuple(field.name for field in dataclasses.fields(ConversationPriorityView))
    assert fields == ("flow_priority", "interaction_phase", "natural_break_available")

    quiet = ConversationPriorityView(
        flow_priority=FlowPriority.PROTECTED,
        interaction_phase=InteractionPhase.WRAP_UP,
        natural_break_available=False,
    )
    busy = ConversationPriorityView(
        flow_priority=FlowPriority.PROTECTED,
        interaction_phase=InteractionPhase.DEEP_EXCHANGE,
        natural_break_available=True,
    )
    assert interruption_cost_band_of(quiet) == interruption_cost_band_of(busy)
    assert interruption_cost_band_of(quiet) == "PROTECTED"
    with pytest.raises(TypeError):
        ConversationPriorityView(  # type: ignore[call-arg]
            flow_priority=FlowPriority.NORMAL,
            interaction_phase=InteractionPhase.OPEN,
        )
