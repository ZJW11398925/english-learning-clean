"""P8-4 ④ — the §13 view's producer, and the one reading both callers share.

``DOMAIN_MODEL §13``'s ``ConversationPriorityView`` had no producer through
P7-2/P7-4; ``DEC-…0f76024b.…3`` R3 moved both the view's production and
``natural_break_available``'s reading to the automatic leg. What is pinned
here:

- the producer's three answers (a live moment ⇒ ``TEACHING / PROTECTED / no
  break``; no lock ⇒ ``OPEN / NORMAL / a break``) and its refusal to guess an
  unknown lock word;
- the **one** reading of BF-02 §5's field
  (``elc.planner.scope.natural_break_available_of``): the shadow run and the
  automatic assembly cannot drift, and a ``None`` view stays the fail-closed
  ``False``;
- the producer is *not* in ``elc.planner.scope`` (that module owns the shape
  and the readings; the producer has to read the durable world);
- the view instance the run reads and the one the controls are derived from
  are the same value — one view, two readers, which is what §13's "expresses
  the protection level and authorizes nothing" needs to stay checkable.
"""

from __future__ import annotations

import ast
import sqlite3
from pathlib import Path

import pytest

from elc.planner.scope import (
    ConversationPriorityView,
    FlowPriority,
    InteractionPhase,
    interruption_cost_band_of,
    natural_break_available_of,
)
from elc.planner.shadow import _natural_break_available_of, run_shadow
from elc.runtime.automatic_controls import automatic_controls_of
from elc.runtime.automatic_teaching import TeachingControlFacts
from elc.runtime.automatic_turn import (
    LOCK_HELD_WORDS,
    LOCK_NONE,
    assemble_automatic_turn,
    conversation_priority_view_of,
)
from tests.conftest import SRC_ROOT
from tests.phase7.conftest import CONV
from tests.phase8.conftest import request_of
from tests.phase8.p8_4_world import (
    World,
    acceptance_supply,
    begin_turn_ok,
    build_content,
    wiring,
    world,
)
from tests.phase8.p8_4_world import coordinator as build_coordinator

AUTOMATIC_TURN_MODULE = SRC_ROOT / "runtime" / "automatic_turn.py"
SCOPE_MODULE = SRC_ROOT / "planner" / "scope.py"
SHADOW_MODULE = SRC_ROOT / "planner" / "shadow.py"


@pytest.fixture()
def content(tmp_path: Path) -> Path:
    return build_content(tmp_path / "content.db")


@pytest.fixture()
def p8world(db: sqlite3.Connection, fence, content: Path) -> World:
    return world(db, fence, content)


# -- ① the producer ----------------------------------------------------------


def test_no_lock_is_an_open_natural_break() -> None:
    view = conversation_priority_view_of(LOCK_NONE)
    assert view.flow_priority is FlowPriority.NORMAL
    assert view.interaction_phase is InteractionPhase.OPEN
    assert view.natural_break_available is True


@pytest.mark.parametrize("word", LOCK_HELD_WORDS)
def test_a_live_lock_is_protected_teaching(word: str) -> None:
    view = conversation_priority_view_of(word)
    assert view.flow_priority is FlowPriority.PROTECTED
    assert view.interaction_phase is InteractionPhase.TEACHING
    assert view.natural_break_available is False


def test_an_unknown_lock_word_is_refused_not_guessed() -> None:
    with pytest.raises(ValueError) as raised:
        conversation_priority_view_of("OWNED_BY_NOBODY")
    message = str(raised.value)
    assert "OWNED_BY_NOBODY" in message
    for word in (LOCK_NONE, *LOCK_HELD_WORDS):
        assert word in message


def test_the_two_words_are_the_durable_lock_vocabulary(db, fence, p8world) -> None:
    """The producer's words are not invented: they are what
    ``TeachingController.observed_lock_state`` answers over this world."""

    assert p8world.teaching.observed_lock_state(CONV).value == LOCK_NONE
    begin_turn_ok(
        build_coordinator(
            p8world, automatic=wiring(p8world, supply=acceptance_supply())
        ),
        "cm-open",
    )
    assert p8world.teaching.observed_lock_state(CONV).value in LOCK_HELD_WORDS


def test_the_producer_reads_a_real_lock_into_the_protected_view(p8world) -> None:
    begin_turn_ok(
        build_coordinator(
            p8world, automatic=wiring(p8world, supply=acceptance_supply())
        ),
        "cm-open",
    )
    lock = p8world.teaching.observed_lock_state(CONV)
    view = conversation_priority_view_of(lock.value)
    assert view.flow_priority is FlowPriority.PROTECTED
    assert view.natural_break_available is False


def test_the_assembly_derives_the_view_from_the_same_lock_read(p8world) -> None:
    plan = assemble_automatic_turn(
        wiring=wiring(p8world, supply=acceptance_supply()),
        conversation_id=CONV,
        decision_cycle_id="dc-p8-4-view",
        as_of="2026-09-23T09:00:00+00:00",
    )
    assert plan.__class__.__name__ == "Ok", plan
    view = plan.value.conversation_priority_view
    assert view is not None
    assert view.flow_priority is FlowPriority.NORMAL
    assert view.natural_break_available is True


def test_a_wiring_without_the_teaching_face_reports_the_leg(p8world) -> None:
    """``observed_lock_state`` is the teaching face's read; a wiring that
    leaves it out gets a note and **no** view (not a fabricated OPEN)."""

    from dataclasses import replace

    bare = replace(
        wiring(p8world, supply=acceptance_supply()),
        teaching=None,  # type: ignore[arg-type]
    )
    plan = assemble_automatic_turn(
        wiring=bare,
        conversation_id=CONV,
        decision_cycle_id="dc-p8-4-view",
        as_of="2026-09-23T09:00:00+00:00",
    )
    assert plan.__class__.__name__ == "Ok", plan
    assert plan.value.conversation_priority_view is None
    assert any("teaching lock" in note for note in plan.value.notes)


# -- ② the shared reading ----------------------------------------------------


def test_the_reading_is_the_view_field() -> None:
    view = ConversationPriorityView(
        flow_priority=FlowPriority.PROTECTED,
        interaction_phase=InteractionPhase.TEACHING,
        natural_break_available=False,
    )
    assert natural_break_available_of(view) is False
    assert (
        natural_break_available_of(
            ConversationPriorityView(
                flow_priority=FlowPriority.NORMAL,
                interaction_phase=InteractionPhase.OPEN,
                natural_break_available=True,
            )
        )
        is True
    )


def test_a_missing_view_is_fail_closed() -> None:
    assert natural_break_available_of(None) is False


def test_the_shadow_adapter_delegates_to_the_shared_reading() -> None:
    """``shadow._natural_break_available_of`` is the request→view adapter: it
    reads one field and hands it to ``elc.planner.scope`` — the module the
    import-set pin gained in the same cut."""

    assert (
        _natural_break_available_of(request_of(conversation_priority_view=None))
        is False
    )
    view = ConversationPriorityView(
        flow_priority=FlowPriority.PROTECTED,
        interaction_phase=InteractionPhase.TEACHING,
        natural_break_available=False,
    )
    assert (
        _natural_break_available_of(request_of(conversation_priority_view=view))
        is False
    )
    open_view = conversation_priority_view_of(LOCK_NONE)
    assert (
        _natural_break_available_of(request_of(conversation_priority_view=open_view))
        is True
    )


def test_the_shadow_run_reads_the_same_field(p8world) -> None:
    """End to end: the value the run's context carries is the view's own field
    (no second derivation on the way)."""

    from tests.phase7.conftest import WATERMARK, proposal
    from tests.phase8.conftest import supply_of

    view = ConversationPriorityView(
        flow_priority=FlowPriority.NORMAL,
        interaction_phase=InteractionPhase.OPEN,
        natural_break_available=True,
    )
    run = run_shadow(
        request_of(conversation_priority_view=view),
        supply=supply_of(proposal("cand-view")),
        current_learning_watermark=WATERMARK,
    )
    assert run.trace.context.natural_break_available is True
    closed = ConversationPriorityView(
        flow_priority=FlowPriority.PROTECTED,
        interaction_phase=InteractionPhase.TEACHING,
        natural_break_available=False,
    )
    run_closed = run_shadow(
        request_of(conversation_priority_view=closed),
        supply=supply_of(proposal("cand-view")),
        current_learning_watermark=WATERMARK,
    )
    assert run_closed.trace.context.natural_break_available is False


def test_the_assembly_and_the_shadow_agree_on_the_same_instance(p8world) -> None:
    """One view, two readers: the plan's view and the run's context carry the
    same field value, and the controls were derived from that same view."""

    plan = assemble_automatic_turn(
        wiring=wiring(p8world, supply=acceptance_supply()),
        conversation_id=CONV,
        decision_cycle_id="dc-p8-4-view",
        as_of="2026-09-23T09:00:00+00:00",
    )
    assert plan.__class__.__name__ == "Ok", plan
    assert (
        plan.value.run.trace.context.natural_break_available
        is plan.value.conversation_priority_view.natural_break_available
    )
    derived = TeachingControlFacts.derived(
        session_budget_view=plan.value.session_budget_view,
        conversation_priority_view=plan.value.conversation_priority_view,
    )
    assert plan.value.controls.hard_protected_flow is derived.hard_protected_flow


def test_the_control_mapping_is_the_shared_one() -> None:
    """The three view-borne controls come from
    ``elc.runtime.automatic_controls``, not from an inline branch here."""

    open_view = conversation_priority_view_of(LOCK_NONE)
    protected = conversation_priority_view_of(LOCK_HELD_WORDS[0])
    for view, expected in ((open_view, False), (protected, True)):
        controls = automatic_controls_of(
            session_budget_view=None, conversation_priority_view=view
        )
        assert controls.hard_protected_flow is expected


def test_the_views_band_reading_is_unchanged() -> None:
    """§13's other reading still maps the three flow words the way P7-2
    declared — the producer adds instances, not vocabulary."""

    assert (
        interruption_cost_band_of(conversation_priority_view_of(LOCK_NONE))
        == "NORMAL"
    )
    assert (
        interruption_cost_band_of(conversation_priority_view_of(LOCK_HELD_WORDS[0]))
        == "PROTECTED"
    )


# -- ③ where the producer lives ----------------------------------------------


def test_the_producer_is_not_in_the_scope_module() -> None:
    source = SCOPE_MODULE.read_text(encoding="utf-8")
    assert "def conversation_priority_view_of" not in source
    assert "def natural_break_available_of" in source


def test_the_producer_lives_in_the_runtime_module() -> None:
    source = AUTOMATIC_TURN_MODULE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }
    assert "conversation_priority_view_of" in functions
    assert "natural_break_available_of" not in functions


def test_the_producer_carries_a_revisit() -> None:
    tree = ast.parse(AUTOMATIC_TURN_MODULE.read_text(encoding="utf-8"))
    producer = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "conversation_priority_view_of"
    )
    doc = ast.get_docstring(producer) or ""
    assert "Revisit:" in doc
    assert "§13" in doc
    assert "authorizes nothing" in doc


def test_the_reading_carries_a_revisit() -> None:
    tree = ast.parse(SCOPE_MODULE.read_text(encoding="utf-8"))
    reader = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "natural_break_available_of"
    )
    doc = ast.get_docstring(reader) or ""
    assert "Revisit:" in doc
    assert "fail-closed" in doc


def test_the_shadow_module_imports_the_reading_not_a_second_copy() -> None:
    tree = ast.parse(SHADOW_MODULE.read_text(encoding="utf-8"))
    imported = [
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    ]
    assert "elc.planner.scope" in imported
