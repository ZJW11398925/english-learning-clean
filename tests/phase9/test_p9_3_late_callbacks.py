"""P9-3 ③ — late callbacks change nothing, and the seven carriers are registered.

STATE_MACHINES §14's late-result rule is the reason this file exists at all:
once a delivery has been cancelled by a barge-in — or refused by §15's
PreDeliveryGuard — the provider result that arrives afterwards is *audited*,
never canonicalized. P9-3 is what makes those two paths able to reach
``TERMINAL`` without a completed reply, so the rule gets the probes it did not
have: a late result must leave the transcript, the §22 row, the §21.1 rows and
the provider-attempt count exactly as they were, and it must still answer the
shipped words (R8: the late-callback vocabulary does **not** move in this cut).

The other half is registration, and deliberately so. §15's seven conditions
each have a V1 carrier, and the carriers are the half a reader cannot check by
looking at the guard's pure output (the point of ``CARRIERS`` below and of the
AST pin over the assembly the controller really builds). Three arms of the
teaching legs are driven here through the coordinator's own assembly with a
stub in the teaching port's shape — the port is the authority the guard asks,
and stubbing it is what lets "the lock is held by another moment" and
"a JUST_CHAT constraint is in force" be *facts of a test* rather than a claim
in a comment.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from elc.platform.db import epoch
from elc.platform.types import (
    ActionId,
    DecisionCycleId,
    DomainErrorCode,
    Err,
    Ok,
    TargetId,
)
from elc.runtime.decision_cycles import DecisionCycleBindings
from elc.runtime.lease import ConversationCoordinatorLease
from elc.runtime.pre_delivery_guard import (
    CONDITION_ATTRIBUTES,
    GuardCondition,
)
from elc.runtime.types import GenerationActionType
from elc.user_config.controller import UserConfigController
from elc.user_config.store import SqliteUserConfigStore
from elc.user_config.types import (
    PlannerConstraint,
    PlannerConstraintScope,
    PlannerConstraintType,
)
from tests.conftest import SRC_ROOT
from tests.phase8.conftest import CONV
from tests.phase9.test_p9_2_stream_turn import (
    REPLY,
    StreamWorld,
    action_of,
    begin_turn_ok,
    count,
    pieces,
    slice_of,
    stream_world,
)
from tests.phase9.test_p9_3_barge_in import (
    InterruptingFactory,
    bind,
    coordinator_for,
    coordinator_over,
    open_turn_with_action,
    second_connection_rows,
)

CONTROLLER = SRC_ROOT / "runtime" / "controller.py"

#: One instant before every window these tests use, so "in force" never depends
#: on the wall clock the coordinator reads.
DAY_ONE = "2026-09-20T09:00:00+00:00"

TARGET = TargetId("res-p9-3-target")

#: §15's seven conditions → the V1 carrier (the reader that answers it) and the
#: test that holds it. Registration, not decoration: the two columns are what a
#: reader needs in order to distrust a carrier, and the AST pin below keeps the
#: first column honest against the assembly's own keywords.
CARRIERS: dict[str, tuple[str, str]] = {
    GuardCondition.CONVERSATION_INACTIVE.value: (
        "the conversation row's status == CLOSED (elc.conversation.store's"
        " own CP0 gate)",
        "test_a_healthy_turn_reads_the_first_five_carriers_as_false",
    ),
    GuardCondition.ACTION_CANCELLED.value: (
        "a pending interrupt_request naming the action",
        "test_the_guard_invalidates_a_delivery_whose_action_is_still_interrupted",
    ),
    GuardCondition.ACTION_SUPERSEDED.value: (
        "the action's turn is not the conversation's latest turn_sequence",
        "test_the_guard_invalidates_a_stale_turns_delivery_as_superseded",
    ),
    GuardCondition.TEACHING_LOCK_INVALID.value: (
        "TeachingController.observed_lock_state != OWNED_BY_THIS_MOMENT",
        "test_the_teaching_lock_leg_answers_none_without_a_face_and_reads_the_lock",
    ),
    GuardCondition.NEW_TARGET_SUPPRESSED.value: (
        "active_constraints_for_target carries SUPPRESS_REVIEW for the"
        " moment's target",
        "test_the_two_constraint_legs_read_the_durable_constraints",
    ),
    GuardCondition.JUST_CHAT_HARD_SWITCH.value: (
        "the §9 view carries JUST_CHAT (elc.planner.scope's own reading)",
        "test_the_two_constraint_legs_read_the_durable_constraints",
    ),
    GuardCondition.LINEAGE_MISMATCH.value: (
        "action.decision_cycle_id vs turn_record.active_decision_cycle_id",
        "test_a_wrong_lineage_is_read_from_the_two_durable_columns",
    ),
}


@pytest.fixture()
def world(tmp_path: Path) -> StreamWorld:
    return stream_world(tmp_path)


# -- the snapshot the late-callback probes compare ----------------------------


def snapshot(
    world: StreamWorld, turn_id: str, action_id: ActionId
) -> dict[str, object]:
    """Every durable fact a late callback could move, read in one place."""

    slice_ = slice_of(world, turn_id)
    delivery = second_connection_rows(
        world,
        "SELECT state, sent_prefix, last_chunk_seq, started_at, terminal_at"
        " FROM server_delivery_record WHERE action_id = ?",
        (str(action_id),),
    )
    guards = second_connection_rows(
        world,
        "SELECT decision FROM pre_delivery_guard_result WHERE action_id = ?"
        " ORDER BY created_at, pre_delivery_guard_result_id",
        (str(action_id),),
    )
    attempts = second_connection_rows(
        world,
        "SELECT COUNT(*) FROM provider_attempt WHERE action_id = ?",
        (str(action_id),),
    )
    assistant = second_connection_rows(
        world,
        "SELECT content, delivery_state FROM assistant_turn WHERE turn_id = ?",
        (turn_id,),
    )
    return {
        "delivery": tuple(delivery[0]) if delivery else None,
        "delivery_state": delivery[0][0] if delivery else None,
        "guard_decisions": tuple(row[0] for row in guards),
        "attempt_count": attempts[0][0],
        "assistant_content": assistant[0][0] if assistant else None,
        "assistant_state": assistant[0][1] if assistant else None,
        "slice_outcome": (
            None if slice_.outcome is None else slice_.outcome.value
        ),
        "assistant_rows": count(world.db, "assistant_turn"),
        "delivery_rows": count(world.db, "server_delivery_record"),
        "guard_rows": count(world.db, "pre_delivery_guard_result"),
        "attempt_rows": count(world.db, "provider_attempt"),
    }


# -- ① the shipped late-callback words ----------------------------------------


def test_a_late_result_for_a_live_action_is_still_a_conflict(
    world: StreamWorld,
) -> None:
    """The shipped third arm, unmoved by this cut: a live nonterminal action
    receiving an out-of-band result is outside the pipeline (V1 has no async
    provider), and the answer is the conflict it always was."""

    _, action_id = open_turn_with_action(world, "cmid-p9-3-late-live")
    result = coordinator_for(world).accept_late_result(action_id, "too early")
    assert isinstance(result, Err), result
    assert result.error.code is DomainErrorCode.CONFLICT


def test_a_late_result_for_a_foreign_epoch_action_is_discarded(
    world: StreamWorld,
) -> None:
    """The second shipped word: an old-epoch action is fenced, so its result is
    audited (RUNTIME §24.1) — the epoch that may not advance an action may not
    canonicalize its output either, and the transcript stays where it was."""

    _, action_id = open_turn_with_action(world, "cmid-p9-3-late-fenced")
    fence2 = epoch.open_runtime_epoch(world.db)
    lease2 = ConversationCoordinatorLease()
    lease2.adopt_epoch(fence2)
    bound = bind(world)
    try:
        coordinator = coordinator_over(bound, lease=lease2)
        before = count(world.db, "assistant_turn")
        result = coordinator.accept_late_result(action_id, "late")
        after = count(world.db, "assistant_turn")
    finally:
        bound.db.close()
    assert isinstance(result, Ok), result
    assert result.value == "DISCARDED_FENCED_EPOCH"
    assert before == after == 0


def test_a_late_result_for_an_interrupted_delivery_changes_nothing(
    world: StreamWorld,
) -> None:
    """A barge-in stopped the stream and left a real durable prefix; the
    provider result that arrives afterwards must leave the transcript (content
    and state), the §22 row (state, prefix, sequence, instants), the §21.1 rows
    and the provider-attempt count byte-for-byte as they were — and it must
    still answer the shipped discard word."""

    chunks = pieces(REPLY, 3)
    factory = InterruptingFactory(world=world, chunks=chunks, after_chunks=1)
    completion = begin_turn_ok(
        coordinator_for(world, transport=factory), "cmid-p9-3-late-partial"
    )
    turn_id = str(completion.turn_id)
    action_id = action_of(world, turn_id)

    before = snapshot(world, turn_id, action_id)
    result = coordinator_for(world).accept_late_result(
        action_id, "the whole answer, arriving too late"
    )
    assert isinstance(result, Ok), result
    assert result.value == "DISCARDED_TERMINAL_ACTION"
    assert snapshot(world, turn_id, action_id) == before
    # the snapshot is not vacuous: this delivery really did send something
    assert before["assistant_content"] == "".join(chunks[:1])
    assert before["delivery_state"] == "CANCELLED"
    assert before["slice_outcome"] == "CANCELLED_BY_USER"
    assert before["attempt_count"] == 1


def test_a_late_result_for_a_guard_invalidated_delivery_changes_nothing(
    world: StreamWorld,
) -> None:
    """The same probe over the other cancellation face: §15 refused the
    delivery before the first release (nothing sent, no transcript row), and a
    late result still finds every count exactly where the verdict left it."""

    coordinator = coordinator_for(world)
    stale_turn, _ = open_turn_with_action(world, "cmid-p9-3-late-stale")
    begin_turn_ok(coordinator, "cmid-p9-3-late-later")
    begin_turn_ok(coordinator, "cmid-p9-3-late-stale")
    stale_action = action_of(world, str(stale_turn))
    assert slice_of(world, str(stale_turn)).assistant_turn is None

    before = snapshot(world, str(stale_turn), stale_action)
    result = coordinator_for(world).accept_late_result(stale_action, "late!")
    assert isinstance(result, Ok), result
    assert result.value == "DISCARDED_TERMINAL_ACTION"
    assert snapshot(world, str(stale_turn), stale_action) == before
    assert before["delivery_state"] == "CANCELLED"
    assert before["assistant_content"] is None
    assert before["guard_decisions"] == ("INVALIDATE_ACTION",)
    assert before["slice_outcome"] == "CANCELLED_BY_USER"


def test_a_late_result_never_rewrites_the_guard_row(world: StreamWorld) -> None:
    """The §21.1 row is a point-in-time verdict (the guard module's reading 6):
    a late callback must not re-run the check or move the row, so the four
    content columns are compared as values across the call."""

    chunks = pieces(REPLY, 3)
    factory = InterruptingFactory(world=world, chunks=chunks, after_chunks=2)
    completion = begin_turn_ok(
        coordinator_for(world, transport=factory), "cmid-p9-3-late-guard"
    )
    action_id = action_of(world, str(completion.turn_id))
    query = (
        "SELECT decision, reason_codes, checked_lineage_version, created_at"
        " FROM pre_delivery_guard_result WHERE action_id = ?"
    )
    before = second_connection_rows(world, query, (str(action_id),))
    coordinator_for(world).accept_late_result(action_id, "late")
    after = second_connection_rows(world, query, (str(action_id),))
    assert before == after
    assert len(after) == 1
    assert after[0][0] == "VALID"


def test_the_late_callback_vocabulary_did_not_move_in_this_cut() -> None:
    """R8 as a source pin: the shipped late-callback face still answers its two
    discard words, and the section that owns them is still the §14 one — the
    cancellation faces this cut added write no word of their own there."""

    text = CONTROLLER.read_text(encoding="utf-8")
    assert "DISCARDED_TERMINAL_ACTION" in text
    assert "DISCARDED_FENCED_EPOCH" in text
    assert "late callback guard (STATE_MACHINES §14)" in text


# -- ② the carrier registry ----------------------------------------------------


def test_the_carrier_table_covers_the_seven_conditions_exactly() -> None:
    """Registration: one row per condition, no extras and none missing — a cut
    that drops a carrier has to delete its row here."""

    assert set(CARRIERS) == {condition.value for condition in GuardCondition}
    assert len(CARRIERS) == 7
    for condition, (carrier, holder) in CARRIERS.items():
        assert carrier, condition
        assert holder, condition


def test_the_assembly_builds_exactly_the_seven_facts_the_module_declares() -> None:
    """The AST pin that keeps the table honest: the controller's one
    ``PreDeliveryGuardFacts(...)`` construction carries one keyword per
    condition, and the keywords are the dataclass's own field names. A carrier
    that is silently dropped (or a field that is never passed) fails here."""

    tree = ast.parse(CONTROLLER.read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "PreDeliveryGuardFacts"
    ]
    assert len(calls) == 1, "one construction site, or this table is not the map"
    keywords = {keyword.arg for keyword in calls[0].keywords}
    assert keywords == set(CONDITION_ATTRIBUTES.values())
    assert len(keywords) == 7


def test_each_carrier_row_names_a_real_test_in_this_phase() -> None:
    """The table's second column is not decoration either: every holder name is
    a real test function in tests/phase9 (the two carrier rows that live in the
    barge-in suite are found there), so a carrier cannot be registered against
    a test that does not exist."""

    import ast as _ast

    names: set[str] = set()
    for path in sorted((SRC_ROOT.parent.parent / "tests" / "phase9").glob("*.py")):
        tree = _ast.parse(path.read_text(encoding="utf-8"))
        names |= {
            node.name
            for node in _ast.walk(tree)
            if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef))
        }
    for condition, (_, holder) in CARRIERS.items():
        assert holder in names, f"{condition} names a missing test: {holder}"


def test_the_guard_row_is_written_once_per_action_and_idempotently(
    world: StreamWorld,
) -> None:
    """One row per action (``guard_result_id_of``'s identity): a second
    submission of the same verdict is the p9-1 store's replay, not a second
    row, and a *different* verdict under the same id is refused — which is what
    makes a §23 re-entry safe rather than a way to rewrite the check."""

    from elc.runtime.delivery_records import PreDeliveryGuardResult
    from elc.runtime.pre_delivery_guard import guard_result_id_of

    completion = begin_turn_ok(coordinator_for(world), "cmid-p9-3-once")
    action_id = action_of(world, str(completion.turn_id))
    rows = second_connection_rows(
        world,
        "SELECT decision, reason_codes, checked_lineage_version, created_at"
        " FROM pre_delivery_guard_result WHERE action_id = ?",
        (str(action_id),),
    )
    assert len(rows) == 1
    replay = world.deliveries.append_pre_delivery_guard_result(
        PreDeliveryGuardResult(
            pre_delivery_guard_result_id=guard_result_id_of(action_id),
            action_id=action_id,
            decision=rows[0][0],
            reason_codes=(),
            checked_lineage_version=rows[0][2],
            created_at=rows[0][3],
        )
    )
    assert isinstance(replay, Ok), replay
    assert (
        count(world.db, "pre_delivery_guard_result") == 1
    ), "a replay must not write a second row"
    rewritten = world.deliveries.append_pre_delivery_guard_result(
        PreDeliveryGuardResult(
            pre_delivery_guard_result_id=guard_result_id_of(action_id),
            action_id=action_id,
            decision="INVALIDATE_ACTION",
            reason_codes=("CONVERSATION_INACTIVE",),
            checked_lineage_version=rows[0][2],
            created_at=rows[0][3],
        )
    )
    assert isinstance(rewritten, Err), rewritten
    assert (
        second_connection_rows(
            world,
            "SELECT decision FROM pre_delivery_guard_result"
            " WHERE action_id = ?",
            (str(action_id),),
        )[0][0]
        == "VALID"
    )


def test_a_late_result_after_a_healthy_reply_is_discarded_and_leaves_it_alone(
    world: StreamWorld,
) -> None:
    """The contrast case the two cancellation probes need: a *complete*
    delivery's late result is discarded by the same shipped word and the
    transcript keeps its full content — so "nothing moved" in the cancelled
    cases is the rule, not an artefact of the snapshot."""

    completion = begin_turn_ok(coordinator_for(world), "cmid-p9-3-late-whole")
    turn_id = str(completion.turn_id)
    action_id = action_of(world, turn_id)
    before = snapshot(world, turn_id, action_id)
    assert before["assistant_content"] == REPLY
    assert before["delivery_state"] == "SENT_COMPLETE"
    result = coordinator_for(world).accept_late_result(action_id, "a second answer")
    assert isinstance(result, Ok), result
    assert result.value == "DISCARDED_TERMINAL_ACTION"
    assert snapshot(world, turn_id, action_id) == before


def test_each_carrier_reader_exists_in_the_controller() -> None:
    """Every carrier names a reader, and every reader is a real call in the
    controller: the assembly is not allowed to name a face it never asks."""

    text = CONTROLLER.read_text(encoding="utf-8")
    for reader in (
        "list_pending_interrupts_for_action",
        "get_sequence_positions",
        "observed_lock_state",
        "active_constraints_for_target",
        "get_planner_constraint_view",
        "active_decision_cycle_id",
        "ConversationStatus.CLOSED",
    ):
        assert reader in text, reader


# -- ③ the carriers, driven ----------------------------------------------------


def test_a_healthy_turn_reads_the_first_five_carriers_as_false(
    world: StreamWorld,
) -> None:
    """The carrier table's first row, plus the four others an ordinary reply
    reaches: the §21.1 row is ``VALID`` with **no** reason code — which is only
    possible if every check ran and answered False (an unread one would spell
    ``UNCHECKED_*``), and the conversation-keyed pending read is empty."""

    completion = begin_turn_ok(coordinator_for(world), "cmid-p9-3-carriers")
    action_id = action_of(world, str(completion.turn_id))
    row = second_connection_rows(
        world,
        "SELECT decision, reason_codes FROM pre_delivery_guard_result"
        " WHERE action_id = ?",
        (str(action_id),),
    )
    assert row == [("VALID", "[]")]
    pending = world.store.list_pending_interrupts_for_conversation(CONV)
    assert isinstance(pending, Ok), pending
    assert pending.value == ()
    conversation = world.store.get_conversation(CONV)
    assert isinstance(conversation, Ok) and conversation.value is not None
    assert conversation.value.status.value == "ACTIVE"


class StubTeaching:
    """The two teaching reads the guard's assembly asks for, answered by hand.

    The guard's port is the *face*, not a controller: what §15's teaching legs
    need are one lock-state word and one moment record, so a test can drive
    "another moment holds the lock" without building a whole teaching chain.
    """

    def __init__(self, *, lock_state: str, moment: object | None) -> None:
        self._lock_state = lock_state
        self._moment = moment

    def observed_lock_state(
        self, conversation_id: object, moment_id: object = None
    ):
        return Ok(self._lock_state)

    def get_moment(self, moment_id: object):
        return Ok(self._moment)


def teaching_action(
    world: StreamWorld, client_message_id: str
) -> tuple[object, ActionId]:
    """One durable turn whose action is a *teaching* delivery.

    The action type is §15's discriminator (the ordinary reply is
    ``NORMAL_PERSONA_REPLY``; the other five §20 types are teaching actions), so
    this action is a teaching delivery that names **no** moment — the shape
    where the lock and target legs are questions with no subject, which is
    exactly the ``None`` arm the tri-state exists for.
    """

    from elc.persona.runtime import action_intent_for_turn

    turn_id, _ = open_turn_with_action(world, client_message_id)
    intent = action_intent_for_turn(
        turn_id=turn_id,
        action_type=GenerationActionType.TEACHING_OPEN,
        generation_contract_id="gc-teaching-open",
        decision_cycle_id=f"dcy-{turn_id}",
    )
    created = world.generation.create_action(intent)
    assert isinstance(created, Ok), created
    turn = world.store.get_turn_record(turn_id)
    assert isinstance(turn, Ok) and turn.value is not None
    return turn.value, created.value


def test_the_teaching_lock_leg_answers_none_without_a_face_and_reads_the_lock(
    world: StreamWorld,
) -> None:
    """The ``TeachingLock invalid`` carrier's two reachable assembly arms: no
    teaching authority at all is ``None`` (unchecked — never "fine"), and with
    the port wired the answer is the lock read's own (a lock held by *another*
    moment, or none at all, is True; §3's carrier for this condition).

    The **False** arm of this leg at the assembly level
    (``OWNED_BY_THIS_MOMENT``) is not here: it needs a durable lock row and a
    real TeachingMoment, i.e. the full teaching chain. That chain landed with
    P9-3's disposition — the real-corpus world opens a real moment and delivers
    its opening (``test_p9_3_teaching_guard.py``), and its guard rows are
    ``VALID`` with the teaching legs read, which is only possible if this leg
    answered ``False`` (a ``True`` would have invalidated the delivery and
    spelled the condition among the row's codes). The pure suite above covers
    the verdict for all three answers.
    """

    turn, action_id = teaching_action(world, "cmid-p9-3-lock")
    action = world.generation.get_action(action_id)
    assert isinstance(action, Ok) and action.value is not None

    none = coordinator_for(world)
    facts = none._pre_delivery_guard_facts(  # noqa: SLF001 — the assembly's own face
        action=action.value, turn=turn, conversation_id=CONV
    )
    assert facts.teaching_lock_invalid is None

    other = coordinator_for(
        world,
        teaching=StubTeaching(lock_state="OWNED_BY_OTHER", moment=None),
    )
    facts = other._pre_delivery_guard_facts(  # noqa: SLF001
        action=action.value, turn=turn, conversation_id=CONV
    )
    assert facts.teaching_lock_invalid is True

    absent = coordinator_for(
        world,
        teaching=StubTeaching(lock_state="NONE", moment=None),
    )
    facts = absent._pre_delivery_guard_facts(  # noqa: SLF001
        action=action.value, turn=turn, conversation_id=CONV
    )
    assert facts.teaching_lock_invalid is True


def test_the_two_constraint_legs_read_the_durable_constraints(
    world: StreamWorld,
) -> None:
    """The two §9 carriers on a real user_config: a ``JUST_CHAT`` switch in
    force makes the target-independent leg True, and the target-scoped
    ``SUPPRESS_REVIEW`` leg answers ``None`` because this teaching action names
    no moment and therefore no target — the two answers of one world. Without
    the constraint face both are ``None`` (the tri-state's other end)."""

    turn, action_id = teaching_action(world, "cmid-p9-3-constraints")
    action = world.generation.get_action(action_id)
    assert isinstance(action, Ok) and action.value is not None

    store = SqliteUserConfigStore(world.db, world.fence)
    for constraint in (
        PlannerConstraint(
            constraint_id="pc-p9-3-just-chat",
            constraint_type=PlannerConstraintType.JUST_CHAT,
            scope=PlannerConstraintScope.UNTIL_USER_REENABLES,
            starts_at=DAY_ONE,
            active=True,
        ),
        PlannerConstraint(
            constraint_id="pc-p9-3-suppress",
            target_type="RESOURCE",
            target_id=TARGET,
            constraint_type=PlannerConstraintType.SUPPRESS_REVIEW,
            scope=PlannerConstraintScope.UNTIL_DATE,
            starts_at=DAY_ONE,
            active=True,
        ),
    ):
        assert isinstance(store.record_planner_constraint(constraint), Ok)

    wired = coordinator_for(
        world,
        teaching=StubTeaching(lock_state="NONE", moment=None),
        constraint_views=UserConfigController(store),
    )
    facts = wired._pre_delivery_guard_facts(  # noqa: SLF001
        action=action.value, turn=turn, conversation_id=CONV
    )
    assert facts.just_chat_hard_switch is True
    assert facts.new_target_suppressed is None
    assert facts.teaching_lock_invalid is True

    # the same world, the same action, no constraint face: both questions are
    # unanswerable rather than "nothing declared".
    unterwired = coordinator_for(
        world,
        teaching=StubTeaching(lock_state="NONE", moment=None),
    )
    facts = unterwired._pre_delivery_guard_facts(  # noqa: SLF001
        action=action.value, turn=turn, conversation_id=CONV
    )
    assert facts.just_chat_hard_switch is None
    assert facts.new_target_suppressed is None


def test_a_wrong_lineage_is_read_from_the_two_durable_columns(
    world: StreamWorld,
) -> None:
    """The lineage carrier has no fake: the two values are the action record's
    ``decision_cycle_id`` and the turn record's
    ``active_decision_cycle_id``. A healthy delivered turn's guard row is
    ``VALID`` with no code (the check ran and answered False), and re-pointing
    the turn at a second cycle through the real store face makes the same read
    answer True — the read *is* the comparison."""

    completion = begin_turn_ok(coordinator_for(world), "cmid-p9-3-lineage")
    turn_id = str(completion.turn_id)
    action_id = action_of(world, turn_id)
    row = second_connection_rows(
        world,
        "SELECT decision, reason_codes FROM pre_delivery_guard_result"
        " WHERE action_id = ?",
        (str(action_id),),
    )
    assert row == [("VALID", "[]")]
    turn_cycle = second_connection_rows(
        world,
        "SELECT active_decision_cycle_id FROM turn_record WHERE turn_id = ?",
        (turn_id,),
    )[0][0]
    action_cycle = second_connection_rows(
        world,
        "SELECT decision_cycle_id FROM generation_action_intent"
        " WHERE action_id = ?",
        (str(action_id),),
    )[0][0]
    assert turn_cycle is not None
    assert action_cycle == turn_cycle

    # a second DecisionCycle in a *live* turn, through the store's own face:
    # the turn's active pointer moves and the action's does not.
    stale_turn, stale_action = open_turn_with_action(
        world, "cmid-p9-3-lineage-open"
    )
    live = world.store.get_turn_record(stale_turn)
    assert isinstance(live, Ok) and live.value is not None
    repointed = world.generation.decision_cycles.record_decision_cycle(
        decision_cycle_id=DecisionCycleId(f"dcy-{stale_turn}-other"),
        turn_id=stale_turn,
        bindings=DecisionCycleBindings(),
        expected_turn_state_version=live.value.state_version,
    )
    assert isinstance(repointed, Ok), repointed
    turn = world.store.get_turn_record(stale_turn)
    action = world.generation.get_action(stale_action)
    assert isinstance(turn, Ok) and turn.value is not None
    assert isinstance(action, Ok) and action.value is not None
    facts = coordinator_for(world)._pre_delivery_guard_facts(  # noqa: SLF001
        action=action.value, turn=turn.value, conversation_id=CONV
    )
    assert facts.lineage_mismatch is True


def test_the_reconcile_runs_before_the_guard_on_the_real_chain(
    world: StreamWorld,
) -> None:
    """Where the two P9-3 faces sit relative to each other and to §15, pinned
    on a real turn: the reconciler ran first (there was nothing to cancel), the
    guard then answered ``VALID`` before the first release, and the delivery
    finished — so a healthy turn's record is one valid verdict, not an absence
    of one."""

    completion = begin_turn_ok(
        coordinator_for(world), "cmid-p9-3-order-of-faces"
    )
    action_id = action_of(world, str(completion.turn_id))
    assert (
        second_connection_rows(
            world,
            "SELECT state FROM server_delivery_record WHERE action_id = ?",
            (str(action_id),),
        )[0][0]
        == "SENT_COMPLETE"
    )
    guards = second_connection_rows(
        world,
        "SELECT decision, reason_codes FROM pre_delivery_guard_result"
        " WHERE action_id = ?",
        (str(action_id),),
    )
    assert guards == [("VALID", "[]")]
