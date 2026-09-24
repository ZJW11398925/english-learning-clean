"""P8-2 ①②③ — docs/DATA_MODEL.md §5.2's ``SessionBudgetView``, derived.

What is pinned here, in the order the cut claims it:

1. **the shape**: the ten §5.2 columns, in the document's order, read out of
   the document at test time; frozen; no defaults (the block spells no ``?``);
   the reading's docstring carries each field's basis and revisit;
2. **the derivation** (:func:`elc.teaching.budget.session_budget_view_of`):
   pure, over the conversation's own rows and one policy port — the usage
   count, the two declared windows, the ``None``-never-``0`` budget legs, the
   absent ``fatigue_signal``, and the refusals (an unreadable instant refuses
   the whole view rather than dropping the row);
3. **the production face** (``TeachingController.get_session_budget_view``):
   the real durable history through the real CP2 unit and the real §5.1 row
   through the real ``UserConfigController``, writing nothing; a controller
   with no policy port refuses rather than reporting a policy it never read;
4. **zero migrations**: no table carries the view, the head is where it was,
   and the consumers the Planner already declares gained no column.
"""

from __future__ import annotations

import dataclasses
import inspect
import os
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from elc.conversation import SqliteConversationStore
from elc.conversation.types import CommitUserTurn
from elc.planner.frontier import MISSING_FRONTIER_AUTHORITIES
from elc.planner.types import PlanningRequest
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.registry import CANONICAL_OBJECTS, OWNER_TEACHING
from elc.platform.types import (
    ActionId,
    ClientMessageId,
    ConversationId,
    DecisionCycleId,
    DomainError,
    DomainErrorCode,
    Err,
    GateDecisionId,
    InputId,
    InteractionChannel,
    MomentId,
    Ok,
    PolicyVersion,
    Result,
    TurnId,
    UserId,
)
from elc.runtime.types import InputEnvelope
from elc.scheduler.spacing import parse_instant
from elc.teaching import budget
from elc.teaching.budget import (
    COOLDOWN_WINDOW_SECONDS,
    RECENT_TEACHING_WINDOW_SECONDS,
    SessionBudgetPolicyPort,
    SessionBudgetPolicySource,
    automatic_probe_moments_used,
    session_budget_view_of,
)
from elc.teaching.controller import TeachingController
from elc.teaching.store import (
    CP2OpenRequest,
    MomentTransition,
    SqliteTeachingStore,
    cp2_action_intent,
)
from elc.teaching.types import (
    AbortReason,
    AuthorizationBasis,
    GateDecisionContext,
    GateDecisionRecord,
    GateDecisionValue,
    GateExecutionStatusRecord,
    GateExecutionStatusValue,
    MomentSource,
    MomentState,
    PresentationPhase,
    SessionBudgetView,
    TeachingMomentRecord,
    TeachingSupportLevel,
    TeachingTargetRef,
)
from elc.user_config.controller import UserConfigController
from elc.user_config.types import TeachingPolicyProfile
from tests.conftest import (
    MIGRATION_IDS,
    REPO_ROOT,
    SCHEMA_HEAD_FILE,
    SCHEMA_HEAD_VERSION,
)
from tests.phase7.conftest import (
    DAY_ONE,
    DAY_TWO,
    TARGET_ID,
    source_text,
    teaching_policy,
)
from tests.phase8.conftest import (
    CONV,
    USER,
    CycleWorld,
    canonical_blocks_verbatim,
    columns_and_vocabulary,
    open_cycle,
)

BUDGET_MODULE = "src/elc/teaching/budget.py"

#: §5.2's own heading for the block this cut turns into a record.
VIEW_HEADING = "### SessionBudgetView"


def _at(minutes: int) -> str:
    """DAY_TWO plus ``minutes`` — the test's own clock, so every cooldown
    assertion is arithmetic a reader can check by hand."""

    return (
        datetime.fromisoformat(DAY_TWO) + timedelta(minutes=minutes)
    ).isoformat()


def _record(
    *,
    conversation_id: ConversationId = CONV,
    moment_id: str = "tm-p8-2-pure",
    source: MomentSource = MomentSource.AUTOMATIC,
    target_mode: str = "RESOURCE_PRACTICE",
    opened_at: str | None = DAY_TWO,
    abort_reason: str | None = None,
    teaching_terminal_at: str | None = None,
) -> TeachingMomentRecord:
    """One §15 *value* for the pure function's inputs.

    The derivation is a function over records, and these are its unit tests;
    the durable half of this suite drives the real CP2 unit instead
    (:func:`_open_moment`), so no fixture supplies a row anywhere.
    """

    return TeachingMomentRecord(
        moment_id=MomentId(moment_id),
        conversation_id=conversation_id,
        persona_id=None,
        source=source,
        decision_cycle_id=DecisionCycleId("dc-p8-2-pure"),
        candidate_id="cand-p8-2",
        gate_decision_id=GateDecisionId(f"gd-{moment_id}"),
        focus_target=TeachingTargetRef("RESOURCE", str(TARGET_ID)),
        supporting_targets=(),
        target_mode=target_mode,
        learning_intent="ESTABLISH",
        evidence_modality="TEXT_PRODUCTION",
        evidence_goal=None,
        preferred_support_ceiling=None,
        learning_snapshot_id=None,
        evidence_watermark=None,
        curriculum_version=None,
        content_version=None,
        policy_version=None,
        lifecycle_state=MomentState.OPENING,
        presentation_phase=PresentationPhase.INITIAL_PROMPT,
        attempt_index=0,
        support_level=TeachingSupportLevel.NONE,
        completion_outcome=None,
        abort_reason=abort_reason,
        state_version=1,
        opened_at=opened_at,
        teaching_terminal_at=teaching_terminal_at,
    )


def _view(
    moments: list[TeachingMomentRecord] | tuple[TeachingMomentRecord, ...],
    *,
    as_of: str = _at(0),
    policy: SessionBudgetPolicyPort | None = None,
    conversation_id: ConversationId = CONV,
) -> SessionBudgetView:
    """The pure derivation's answer, unwrapped (the test fails on an Err)."""

    result = session_budget_view_of(
        conversation_id=conversation_id,
        as_of=as_of,
        policy=policy,
        moments=moments,
    )
    assert isinstance(result, Ok), result
    return result.value


@dataclass(frozen=True)
class _Policy:
    """A policy value as the narrow port declares it: the version, no more."""

    policy_version: PolicyVersion | None


class _BoundPolicySource:
    """The port's implementation shape a caller wires: a user binding around
    the real §5.1 read face.

    ``SessionBudgetPolicySource``'s user leg has to come from somewhere
    (DATA_MODEL §3's Conversation carries no ``user_id`` and the conversation
    store discards the argument), so the assembly that wires the controller is
    where it is decided — this is that assembly, in four lines.
    """

    def __init__(self, controller: UserConfigController, user_id: UserId) -> None:
        self._controller = controller
        self._user = user_id

    @property
    def user_id(self) -> UserId:
        return self._user

    def get_teaching_policy(self, user_id: UserId) -> Result[Any]:
        return self._controller.get_teaching_policy(user_id)


class _RefusingPolicySource:
    """A policy read that fails — the view must return that Err verbatim."""

    @property
    def user_id(self) -> UserId:
        return USER

    def get_teaching_policy(self, user_id: UserId) -> Result[Any]:
        del user_id
        return Err(
            DomainError(
                code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                message="injected: policy unreadable",
            )
        )


# -- ① the shape -------------------------------------------------------------


def test_the_view_is_the_canonical_block_word_for_word() -> None:
    """§5.2's block, read out of the document: ten columns, this order."""

    (block,) = canonical_blocks_verbatim("DATA_MODEL.md", VIEW_HEADING)
    columns, vocabulary = columns_and_vocabulary(block)
    assert columns == (
        "conversation_id",
        "policy_version",
        "automatic_teaching_used",
        "automatic_teaching_remaining",
        "probe_budget_remaining",
        "cooldown_remaining",
        "recent_skips",
        "recent_rejections",
        "fatigue_signal",
        "as_of",
    )
    assert vocabulary == ()
    assert tuple(
        field.name for field in dataclasses.fields(SessionBudgetView)
    ) == columns


def test_the_view_is_frozen_and_states_every_field() -> None:
    """No defaults: §5.2 spells no ``?`` on this block, so a caller states
    every column (the ``ScheduleView`` contrast is §5.2's own)."""

    assert dataclasses.fields(SessionBudgetView)
    assert dataclasses.is_dataclass(SessionBudgetView)
    for field in dataclasses.fields(SessionBudgetView):
        assert field.default is dataclasses.MISSING, field.name
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(_view(()), "recent_skips", 3)


def test_the_view_carries_the_declared_types_and_the_none_semantics() -> None:
    """The two budget legs admit ``None`` (no vocabulary was read); the
    cooldown is a number (floored) and the rest are counts/words."""

    hints = {
        field.name: field.type for field in dataclasses.fields(SessionBudgetView)
    }
    assert hints["automatic_teaching_remaining"] == "int | None"
    assert hints["probe_budget_remaining"] == "int | None"
    assert hints["fatigue_signal"] == "str | None"
    assert hints["cooldown_remaining"] == "float"
    assert hints["as_of"] == "str"


def test_the_view_and_the_derivation_cite_their_canonical_authorities() -> None:
    """§5.2 (the block), §13 (the two authorities), §10 (Planner input, not
    Learning State) and the derived-view fact, each quoted where a reader
    starts."""

    view_doc = SessionBudgetView.__doc__ or ""
    for phrase in (
        "Derived view",
        "§5.2",
        "§13",
        "TeachingPolicyProfile",
        "Planner input",
        "Learning State",
        "one session is",
    ):
        assert phrase in view_doc, phrase
    module_doc = budget.__doc__ or ""
    for phrase in (
        "DATA_MODEL.md §5.2",
        "DOMAIN_MODEL.md §13",
        "Planner input",
        "Derived view",
        "no table",
    ):
        assert phrase in module_doc, phrase


def test_every_derived_reading_carries_a_revisit() -> None:
    """The module's per-field list names a Revisit for the readings it
    declares (the house rule the planner modules pin the same way)."""

    module_doc = budget.__doc__ or ""
    assert module_doc.count("Revisit") >= 8, module_doc.count("Revisit")
    start = module_doc.index("**Per-field derivation**")
    end = module_doc.index("**Instants, and what")
    per_field = module_doc[start:end]
    for field in (
        "conversation_id",
        "policy_version",
        "automatic_teaching_used",
        "cooldown_remaining",
        "recent_skips",
        "fatigue_signal",
        "as_of",
    ):
        assert field in per_field, field
    assert per_field.count("Revisit") >= 6, per_field.count("Revisit")


def test_the_two_windows_are_declared_constants_with_their_reasons() -> None:
    """BF-03 §17 and IP pin no number, so this cut declares the two — stated
    once, separately, and never presented as canonical."""

    assert COOLDOWN_WINDOW_SECONDS == 1800.0
    assert RECENT_TEACHING_WINDOW_SECONDS == 3600.0
    source = source_text(BUDGET_MODULE)
    cooldown_block = source[: source.index("COOLDOWN_WINDOW_SECONDS: float")]
    recent_block = source[: source.index("RECENT_TEACHING_WINDOW_SECONDS: float")]
    assert "BF-03 §17" in cooldown_block
    assert "Revisit" in cooldown_block
    assert "separate" in recent_block
    assert "Revisit" in recent_block


# -- ② the derivation, as a function ----------------------------------------


def test_an_empty_history_answers_the_honest_zero_view() -> None:
    """No rows, no policy: counts and cooldown are real zeros, the two budget
    legs are ``None`` (no vocabulary was read), and the policy version is
    ``None`` (no row was read) — never an invented one."""

    view = _view(())
    assert view.automatic_teaching_used == 0
    assert view.cooldown_remaining == 0.0
    assert view.recent_skips == 0
    assert view.recent_rejections == 0
    assert view.automatic_teaching_remaining is None
    assert view.probe_budget_remaining is None
    assert view.fatigue_signal is None
    assert view.policy_version is None
    assert view.as_of == _at(0)


def test_a_busy_session_still_invents_no_fatigue_signal() -> None:
    """``fatigue_signal`` is absent as a claim about the *field*, not about a
    quiet conversation: six automatic openings — past any threshold a "tired
    user" heuristic might read a usage count against — still answer ``None``,
    while the facts the view does derive stay exactly what the rows say.

    The mutation this pins (the p8-2 review's m12): a producer that turns
    ``automatic_teaching_used`` into a word once it passes some threshold.
    The empty-history case above covers ``None`` only where the count is
    zero, so it folds silently. Here the count is 6."""

    view = _view(
        [
            _record(moment_id=f"tm-busy-{index}", opened_at=_at(index))
            for index in range(6)
        ],
        as_of=_at(10),
    )
    assert view.automatic_teaching_used == 6
    assert view.fatigue_signal is None
    # The derived facts a busy session does state are unaffected: the newest
    # opening (at +5) leaves the declared cooldown running, and nothing was
    # closed, so both recency counts are real zeros.
    assert view.cooldown_remaining == COOLDOWN_WINDOW_SECONDS - 5 * 60
    assert view.recent_skips == 0
    assert view.recent_rejections == 0


def test_the_view_counts_only_its_own_conversations_rows() -> None:
    """Two conversations sharing a user are the ordinary case; a budget is per
    session, so another conversation's row is not this view's fact."""

    other = ConversationId("conv-p8-2-other")
    view = _view(
        [
            _record(moment_id="tm-mine"),
            _record(moment_id="tm-other", conversation_id=other),
        ]
    )
    assert view.automatic_teaching_used == 1


@pytest.mark.parametrize(
    "source",
    [
        MomentSource.USER_INITIATED,
        MomentSource.MANUAL_FOCUS,
        MomentSource.SCHEDULED_STUDY,
    ],
)
def test_only_automatic_openings_are_automatic_usage(
    source: MomentSource,
) -> None:
    """§5.2's ``automatic_teaching_used`` is the automatic half: a user's own
    opening is not the automatic budget being spent."""

    view = _view([_record(moment_id="tm-x", source=source)])
    assert view.automatic_teaching_used == 0
    assert view.cooldown_remaining == 0.0


def test_closed_and_live_automatic_moments_both_count() -> None:
    """The usage leg is the conversation's history, not its active moment."""

    view = _view(
        [
            _record(
                moment_id="tm-closed",
                abort_reason=AbortReason.POLICY_STOP.value,
                teaching_terminal_at=_at(1),
            ),
            _record(moment_id="tm-live", opened_at=_at(2)),
        ],
        as_of=_at(5),
    )
    assert view.automatic_teaching_used == 2


def test_the_cooldown_is_the_declared_window_minus_the_elapsed_time() -> None:
    """An opening twenty minutes ago leaves ten of the declared thirty."""

    view = _view([_record(opened_at=DAY_TWO)], as_of=_at(20))
    assert view.cooldown_remaining == COOLDOWN_WINDOW_SECONDS - 20 * 60


@pytest.mark.parametrize(
    "minutes,expected",
    [
        (0, 1800.0),
        (1, 1740.0),
        (29, 60.0),
        (30, 0.0),
        (31, 0.0),
        (600, 0.0),
    ],
)
def test_the_cooldown_is_floored_at_zero(minutes: int, expected: float) -> None:
    """The window is inclusive at its near edge and floored beyond it: the
    boundary instant is already ``0.0`` (no time is left)."""

    view = _view([_record(opened_at=DAY_TWO)], as_of=_at(minutes))
    assert view.cooldown_remaining == expected


def test_a_user_initiated_opening_starts_no_cooldown() -> None:
    """BF-03 §17's cooldown guards *automatic* openings; the user's own
    opening is not the throttled act."""

    view = _view(
        [_record(source=MomentSource.USER_INITIATED, opened_at=DAY_TWO)],
        as_of=_at(1),
    )
    assert view.cooldown_remaining == 0.0
    assert view.automatic_teaching_used == 0


def test_the_newest_automatic_opening_is_the_anchor() -> None:
    """Two automatic openings: the cooldown is measured from the newer one."""

    view = _view(
        [
            _record(moment_id="tm-old", opened_at=DAY_TWO),
            _record(moment_id="tm-new", opened_at=_at(10)),
        ],
        as_of=_at(20),
    )
    assert view.cooldown_remaining == COOLDOWN_WINDOW_SECONDS - 10 * 60


def test_an_opening_after_as_of_has_not_started_a_cooldown_yet() -> None:
    """``as_of`` classifies: an opening that had not happened at the
    classification instant cannot have started a cooldown *at* it. The usage
    count stays the durable-row count the module docstring declares."""

    view = _view([_record(opened_at=_at(60))], as_of=_at(0))
    assert view.cooldown_remaining == 0.0
    assert view.automatic_teaching_used == 1


def test_the_two_counts_read_the_two_canonical_words() -> None:
    view = _view(
        [
            _record(
                moment_id="tm-skip",
                abort_reason=AbortReason.USER_SKIP.value,
                teaching_terminal_at=_at(1),
            ),
            _record(
                moment_id="tm-reject",
                abort_reason=AbortReason.USER_REJECTED_TARGET.value,
                teaching_terminal_at=_at(2),
            ),
        ],
        as_of=_at(5),
    )
    assert view.recent_skips == 1
    assert view.recent_rejections == 1


@pytest.mark.parametrize(
    "reason",
    sorted(
        reason.value
        for reason in AbortReason
        if reason not in (AbortReason.USER_SKIP, AbortReason.USER_REJECTED_TARGET)
    ),
)
def test_no_other_abort_reason_counts_as_a_skip_or_rejection(reason: str) -> None:
    """§7's other twelve closures are their own facts; the view counts the two
    §5.2 names and no others."""

    view = _view(
        [
            _record(
                moment_id="tm-other",
                abort_reason=reason,
                teaching_terminal_at=_at(1),
            )
        ],
        as_of=_at(5),
    )
    assert view.recent_skips == 0
    assert view.recent_rejections == 0


def test_a_closure_outside_the_recent_window_is_not_counted() -> None:
    """The window's far edge is inclusive; one minute beyond it is out."""

    def skips_at(minutes: int) -> int:
        return _view(
            [
                _record(
                    moment_id="tm-skip",
                    abort_reason=AbortReason.USER_SKIP.value,
                    teaching_terminal_at=DAY_TWO,
                )
            ],
            as_of=_at(minutes),
        ).recent_skips

    assert skips_at(59) == 1
    assert skips_at(60) == 1  # exactly one window: still inside
    assert skips_at(61) == 0


def test_a_closure_after_as_of_has_not_happened_at_as_of() -> None:
    view = _view(
        [
            _record(
                moment_id="tm-skip",
                abort_reason=AbortReason.USER_SKIP.value,
                teaching_terminal_at=_at(5),
            )
        ],
        as_of=_at(0),
    )
    assert view.recent_skips == 0


def test_the_two_budget_legs_are_none_not_zero_with_a_policy_present() -> None:
    """§5.1 pins no budget vocabulary, so nothing is subtractable — and
    ``None`` keeps "unreadable" apart from "spent"."""

    view = _view((), policy=_Policy(policy_version=PolicyVersion("pv-p8-2")))
    assert view.policy_version == PolicyVersion("pv-p8-2")
    assert view.automatic_teaching_remaining is None
    assert view.probe_budget_remaining is None
    assert view.fatigue_signal is None


def test_the_policy_port_names_the_version_and_no_budget_column() -> None:
    """The narrow port: the budget column is deliberately unnamed so no code
    here can parse it into a number this cut may not invent."""

    annotations = getattr(SessionBudgetPolicyPort, "__annotations__", None)
    assert annotations is not None
    assert set(annotations) == {"policy_version"}
    source = source_text(BUDGET_MODULE)
    assert "interruption_budget" in source  # named, and only in prose
    assert "interruption_budget:" not in source


def test_the_source_port_carries_the_user_leg_and_one_read() -> None:
    """Two members and no more: the user binding (which nothing else can
    supply) and the §5.1 read."""

    members = {
        name for name in dir(SessionBudgetPolicySource) if not name.startswith("__")
    }
    assert "user_id" in members
    assert "get_teaching_policy" in members
    annotations = SessionBudgetPolicySource.get_teaching_policy.__annotations__
    assert set(annotations) >= {"user_id", "return"}


def test_the_probe_usage_is_readable_without_the_vocabulary() -> None:
    """The usage leg §5.2's ``probe_budget_remaining`` would subtract from:
    automatic §11 ``PROBE`` openings, closed or live."""

    moments = [
        _record(moment_id="tm-probe", target_mode="PROBE"),
        _record(moment_id="tm-practice", target_mode="RESOURCE_PRACTICE"),
        _record(
            moment_id="tm-user-probe",
            source=MomentSource.USER_INITIATED,
            target_mode="PROBE",
        ),
        _record(
            moment_id="tm-probe-closed",
            target_mode="PROBE",
            abort_reason=AbortReason.POLICY_STOP.value,
            teaching_terminal_at=_at(1),
        ),
    ]
    assert (
        automatic_probe_moments_used(conversation_id=CONV, moments=moments) == 2
    )


def test_the_derivation_is_reproducible() -> None:
    """Two calls over one world answer identically (the ``as_of`` precedent:
    a view is reproducible or it is not a view)."""

    moments = [_record(), _record(moment_id="tm-2", opened_at=_at(10))]
    assert _view(moments, as_of=_at(15)) == _view(moments, as_of=_at(15))


@pytest.mark.parametrize(
    "as_of",
    ["", "not-an-instant", "2026-09-23T09:00:00"],
)
def test_an_unusable_as_of_refuses_the_view(as_of: str) -> None:
    result = session_budget_view_of(
        conversation_id=CONV, as_of=as_of, policy=None, moments=()
    )
    assert isinstance(result, Err)
    assert result.error.code.value == "VALIDATION_FAILED"
    assert "as_of" in result.error.message


@pytest.mark.parametrize(
    "opened_at",
    ["", "yesterday", "2026-09-23T09:00:00"],
)
def test_an_unusable_opening_instant_refuses_the_whole_view(
    opened_at: str,
) -> None:
    """Never a dropped row: a view that skipped it would understate the
    budget the Gate reads (the Scheduler view's own rule)."""

    result = session_budget_view_of(
        conversation_id=CONV,
        as_of=_at(5),
        policy=None,
        moments=[_record(opened_at=opened_at)],
    )
    assert isinstance(result, Err)
    assert result.error.code.value == "VALIDATION_FAILED"
    assert "opened_at" in result.error.message


def test_a_closure_with_no_instant_refuses_the_whole_view() -> None:
    """A §7 reason with no closure instant cannot be placed in time."""

    result = session_budget_view_of(
        conversation_id=CONV,
        as_of=_at(5),
        policy=None,
        moments=[
            _record(
                abort_reason=AbortReason.USER_SKIP.value,
                teaching_terminal_at=None,
            )
        ],
    )
    assert isinstance(result, Err)
    assert result.error.code.value == "VALIDATION_FAILED"
    assert "teaching_terminal_at" in result.error.message


@pytest.mark.parametrize(
    "text,clause",
    [
        ("", "is empty"),
        ("not-an-instant", "is not an ISO-8601 timestamp"),
        ("2026-09-23T09:00:00", "carries no UTC offset"),
    ],
)
def test_the_instant_ruler_agrees_with_the_schedulers(
    text: str, clause: str
) -> None:
    """Third declaration, one reading: this module restates the Scheduler's
    three refusals rather than importing them (the ``user_config.store``
    precedent), so the two are pinned equal here — same refusal class, same
    code, same clause naming what was wrong. The acting subject is each
    module's own word ("this policy" / "this derivation"), which is what the
    two restatements differ in and all they differ in.
    """

    ours = budget._parse_instant(text, field="as_of")
    theirs = parse_instant(text, field="as_of")
    assert isinstance(ours, Err) and isinstance(theirs, Err)
    assert ours.error.code is theirs.error.code
    assert clause in ours.error.message
    assert clause in theirs.error.message
    assert ours.error.message.startswith("as_of")


def test_the_instant_ruler_accepts_the_same_instants() -> None:
    for text in (DAY_ONE, "2026-09-23T09:00:00+08:00", "2026-09-23T09:00:00Z"):
        ours = budget._parse_instant(text, field="as_of")
        theirs = parse_instant(text, field="as_of")
        assert isinstance(ours, Ok) and isinstance(theirs, Ok)
        assert ours.value == theirs.value


# -- ③ the production face, over the durable world --------------------------


@pytest.fixture()
def teaching_store(
    db: sqlite3.Connection, fence: RuntimeEpochFence
) -> SqliteTeachingStore:
    return SqliteTeachingStore(db, fence)


@pytest.fixture()
def teaching_controller(
    teaching_store: SqliteTeachingStore,
    user_config_controller: UserConfigController,
) -> TeachingController:
    return TeachingController(
        teaching_store, policy=_BoundPolicySource(user_config_controller, USER)
    )


def _open_moment(
    store: SqliteTeachingStore,
    fence: RuntimeEpochFence,
    *,
    cycle: CycleWorld,
    moment_id: str,
    conversation_id: ConversationId = CONV,
    source: MomentSource = MomentSource.AUTOMATIC,
    target_mode: str = "RESOURCE_PRACTICE",
    opened_at: str | None = None,
    created_at: str | None = None,
) -> MomentId:
    """One durable moment, through the store's own CP2 five-fact unit.

    The five records are the test's (the unit's caller is whoever holds the
    facts); the write is the real atomic unit, so every row this suite reads
    was written the production way. ``opened_at`` / ``created_at`` are the
    caller's declarations when given — the store stamps its own clock
    otherwise.
    """

    opened = store.open_teaching_moment(
        CP2OpenRequest(
            gate_execution_status=GateExecutionStatusRecord(
                gate_execution_status_id=f"ges-{moment_id}",
                decision_cycle_id=cycle.decision_cycle_id,
                moment_id=None,
                gate_context=GateDecisionContext.OPEN,
                authorization_basis=AuthorizationBasis.DECISION_CYCLE,
                authorization_status="VALID",
                status=GateExecutionStatusValue.SUCCEEDED,
                missing_or_unknown=(),
            ),
            gate_decision=GateDecisionRecord(
                gate_decision_id=GateDecisionId(f"gd-{moment_id}"),
                decision_cycle_id=cycle.decision_cycle_id,
                candidate_id="cand-p8-2",
                context=GateDecisionContext.OPEN,
                decision=GateDecisionValue.ALLOW,
                reason_codes=(),
                policy_version=PolicyVersion("pv-p8-2"),
            ),
            moment=TeachingMomentRecord(
                moment_id=MomentId(moment_id),
                conversation_id=conversation_id,
                persona_id=None,
                source=source,
                decision_cycle_id=cycle.decision_cycle_id,
                candidate_id="cand-p8-2",
                gate_decision_id=GateDecisionId(f"gd-{moment_id}"),
                focus_target=TeachingTargetRef("RESOURCE", str(TARGET_ID)),
                supporting_targets=(),
                target_mode=target_mode,
                learning_intent="ESTABLISH",
                evidence_modality="TEXT_PRODUCTION",
                evidence_goal=None,
                preferred_support_ceiling=None,
                learning_snapshot_id=None,
                evidence_watermark=None,
                curriculum_version=None,
                content_version=None,
                policy_version=None,
                lifecycle_state=MomentState.OPENING,
                presentation_phase=PresentationPhase.INITIAL_PROMPT,
                attempt_index=0,
                support_level=TeachingSupportLevel.NONE,
                completion_outcome=None,
                abort_reason=None,
                state_version=1,
                created_at=created_at,
                opened_at=opened_at,
            ),
            action=cp2_action_intent(
                turn_id=cycle.turn_id,
                moment_id=MomentId(moment_id),
                decision_cycle_id=cycle.decision_cycle_id,
                action_id=ActionId(f"ga-{moment_id}"),
                assistant_turn_id=f"aturn-{moment_id}",
                generation_contract_id="gc-teaching-open",
                owner_epoch=fence.current,
            ),
            owner_epoch=fence.current,
        )
    )
    assert isinstance(opened, Ok), opened
    assert str(opened.value) == moment_id
    return opened.value


def _close_moment(
    store: SqliteTeachingStore, moment_id: MomentId, *, abort_reason: str
) -> None:
    """ABORTING then TEACHING_TERMINAL — the store's own two steps, so the
    closure instant is the store's clock and never a test's."""

    advanced = store.transition_moment(
        moment_id,
        MomentTransition(lifecycle_state=MomentState.ABORTING),
        expected_state_version=1,
    )
    assert isinstance(advanced, Ok), advanced
    closed = store.terminalize_moment(moment_id, abort_reason=abort_reason)
    assert isinstance(closed, Ok), closed
    assert closed.value.abort_reason == abort_reason
    assert closed.value.teaching_terminal_at is not None


def _write_policy(
    user_config_controller: UserConfigController, *, version: str
) -> None:
    written = user_config_controller.upsert_teaching_policy(
        teaching_policy(version=version)
    )
    assert isinstance(written, Ok), written


def test_the_view_reads_the_real_history_through_the_real_faces(
    db: sqlite3.Connection,
    fence: RuntimeEpochFence,
    cycle: CycleWorld,
    teaching_store: SqliteTeachingStore,
    teaching_controller: TeachingController,
    user_config_controller: UserConfigController,
) -> None:
    """A durable automatic opening with a caller-declared instant, a §5.1
    policy row, and the view over both — every number traceable to a row."""

    _write_policy(user_config_controller, version="pv-p8-2")
    _open_moment(
        teaching_store,
        fence,
        cycle=cycle,
        moment_id="tm-p8-2-real",
        opened_at=DAY_TWO,
    )
    view_result = teaching_controller.get_session_budget_view(CONV, _at(20))
    assert isinstance(view_result, Ok), view_result
    view = view_result.value

    assert view.conversation_id == CONV
    assert view.policy_version == PolicyVersion("pv-p8-2")
    assert view.automatic_teaching_used == 1
    assert view.cooldown_remaining == COOLDOWN_WINDOW_SECONDS - 20 * 60
    assert view.recent_skips == 0
    assert view.recent_rejections == 0
    assert view.automatic_teaching_remaining is None
    assert view.probe_budget_remaining is None
    assert view.fatigue_signal is None
    assert view.as_of == _at(20)


def test_a_closed_skip_is_counted_through_the_durable_world(
    db: sqlite3.Connection,
    fence: RuntimeEpochFence,
    cycle: CycleWorld,
    teaching_store: SqliteTeachingStore,
    teaching_controller: TeachingController,
    user_config_controller: UserConfigController,
) -> None:
    """The closure instant is the store's clock, so "recent" is asserted
    against two ``as_of`` values the test chooses: inside the window, and a
    day beyond it."""

    _write_policy(user_config_controller, version="pv-p8-2")
    moment_id = _open_moment(
        teaching_store, fence, cycle=cycle, moment_id="tm-p8-2-skip"
    )
    _close_moment(teaching_store, moment_id, abort_reason="USER_SKIP")

    now = datetime.now(UTC)
    inside = teaching_controller.get_session_budget_view(CONV, now.isoformat())
    assert isinstance(inside, Ok), inside
    assert inside.value.recent_skips == 1
    assert inside.value.recent_rejections == 0
    assert inside.value.automatic_teaching_used == 1

    later = teaching_controller.get_session_budget_view(
        CONV, (now + timedelta(days=1)).isoformat()
    )
    assert isinstance(later, Ok), later
    assert later.value.recent_skips == 0


def test_a_user_initiated_moment_is_not_automatic_usage_over_the_store(
    db: sqlite3.Connection,
    fence: RuntimeEpochFence,
    cycle: CycleWorld,
    teaching_store: SqliteTeachingStore,
    teaching_controller: TeachingController,
    user_config_controller: UserConfigController,
) -> None:
    _write_policy(user_config_controller, version="pv-p8-2")
    _open_moment(
        teaching_store,
        fence,
        cycle=cycle,
        moment_id="tm-p8-2-user",
        source=MomentSource.USER_INITIATED,
        opened_at=DAY_TWO,
    )
    view_result = teaching_controller.get_session_budget_view(CONV, _at(5))
    assert isinstance(view_result, Ok), view_result
    assert view_result.value.automatic_teaching_used == 0
    assert view_result.value.cooldown_remaining == 0.0


def test_the_probe_count_face_reads_the_durable_rows(
    db: sqlite3.Connection,
    fence: RuntimeEpochFence,
    cycle: CycleWorld,
    teaching_store: SqliteTeachingStore,
    teaching_controller: TeachingController,
) -> None:
    _open_moment(
        teaching_store,
        fence,
        cycle=cycle,
        moment_id="tm-p8-2-probe",
        target_mode="PROBE",
    )
    counted = teaching_controller.count_automatic_probe_moments(CONV)
    assert isinstance(counted, Ok), counted
    assert counted.value == 1
    other = teaching_controller.count_automatic_probe_moments(
        ConversationId("conv-p8-2-absent")
    )
    assert isinstance(other, Ok)
    assert other.value == 0


def test_the_view_writes_nothing(
    db: sqlite3.Connection,
    fence: RuntimeEpochFence,
    cycle: CycleWorld,
    teaching_store: SqliteTeachingStore,
    teaching_controller: TeachingController,
    user_config_controller: UserConfigController,
) -> None:
    """A view is a read: the durable world is exactly where it was."""

    _write_policy(user_config_controller, version="pv-p8-2")
    _open_moment(teaching_store, fence, cycle=cycle, moment_id="tm-p8-2-rd")
    before_changes = db.total_changes
    before_rows = db.execute("SELECT COUNT(*) FROM teaching_moment").fetchone()[0]
    for as_of in (_at(0), _at(20), _at(600)):
        assert isinstance(
            teaching_controller.get_session_budget_view(CONV, as_of), Ok
        )
        assert isinstance(
            teaching_controller.count_automatic_probe_moments(CONV), Ok
        )
    assert db.total_changes == before_changes
    assert (
        db.execute("SELECT COUNT(*) FROM teaching_moment").fetchone()[0]
        == before_rows
    )


def test_a_controller_without_the_policy_port_refuses(
    teaching_store: SqliteTeachingStore,
) -> None:
    """No policy read face ⇒ ``DEPENDENCY_UNAVAILABLE``, not a view whose
    ``policy_version=None`` conflates "never written" with "never read"."""

    bare = TeachingController(teaching_store)
    refused = bare.get_session_budget_view(CONV, _at(0))
    assert isinstance(refused, Err)
    assert refused.error.code.value == "DEPENDENCY_UNAVAILABLE"
    assert "policy" in refused.error.message
    # The probe count needs no policy leg and still answers.
    assert isinstance(bare.count_automatic_probe_moments(CONV), Ok)


def test_a_failing_policy_read_is_returned_verbatim(
    teaching_store: SqliteTeachingStore,
) -> None:
    controller = TeachingController(
        teaching_store, policy=_RefusingPolicySource()
    )
    refused = controller.get_session_budget_view(CONV, _at(0))
    assert isinstance(refused, Err)
    assert "policy unreadable" in refused.error.message


def test_no_policy_row_answers_none_without_inventing_a_version(
    db: sqlite3.Connection,
    fence: RuntimeEpochFence,
    cycle: CycleWorld,
    teaching_store: SqliteTeachingStore,
    teaching_controller: TeachingController,
) -> None:
    """The port is wired, the user never wrote a policy: ``None``, and the
    rest of the view still reads."""

    _open_moment(teaching_store, fence, cycle=cycle, moment_id="tm-p8-2-np")
    view_result = teaching_controller.get_session_budget_view(CONV, _at(1))
    assert isinstance(view_result, Ok), view_result
    assert view_result.value.policy_version is None
    assert view_result.value.automatic_teaching_used == 1


def test_the_durable_read_is_keyed_by_the_conversation(
    db: sqlite3.Connection,
    fence: RuntimeEpochFence,
    cycle: CycleWorld,
    teaching_store: SqliteTeachingStore,
    teaching_controller: TeachingController,
    user_config_controller: UserConfigController,
) -> None:
    """Two conversations, two moments: each view sees exactly its own."""

    _write_policy(user_config_controller, version="pv-p8-2")
    other = ConversationId("conv-p8-2-second")
    other_cycle = _other_conversation_cycle(db, fence, conversation_id=other)
    _open_moment(teaching_store, fence, cycle=cycle, moment_id="tm-conv-a")
    _open_moment(
        teaching_store,
        fence,
        cycle=other_cycle,
        moment_id="tm-conv-b",
        conversation_id=other,
    )
    mine = teaching_controller.get_session_budget_view(CONV, _at(0))
    theirs = teaching_controller.get_session_budget_view(other, _at(0))
    assert isinstance(mine, Ok) and isinstance(theirs, Ok)
    assert mine.value.automatic_teaching_used == 1
    assert theirs.value.automatic_teaching_used == 1
    assert mine.value.conversation_id == CONV
    assert theirs.value.conversation_id == other


def _other_conversation_cycle(
    db: sqlite3.Connection,
    fence: RuntimeEpochFence,
    *,
    conversation_id: ConversationId,
) -> CycleWorld:
    """A second conversation with its own CP0 turn and cycle (real faces)."""

    store = SqliteConversationStore(db, fence)
    opened = store.open_conversation(
        conversation_id, user_id=USER, persona_id=None, scene_id=None
    )
    assert isinstance(opened, Ok), opened
    commit = store.commit_user_turn(
        CommitUserTurn(
            conversation_id=conversation_id,
            envelope=InputEnvelope(
                input_id=InputId(f"in-{conversation_id}"),
                client_message_id=ClientMessageId(f"cmid-{conversation_id}"),
                conversation_id=str(conversation_id),
                persona_id=None,
                scene_id=None,
                interaction_channel=InteractionChannel.TEXT,
                raw_payload="raw-p8-2-other",
                received_at=DAY_TWO,
            ),
            raw_content="Another conversation's turn.",
            runtime_version="runtime-p8-2",
            turn_id=TurnId(f"turn-{conversation_id}"),
        )
    )
    assert isinstance(commit, Ok), commit
    return open_cycle(
        db,
        fence,
        decision_cycle_id=DecisionCycleId(f"dc-{conversation_id}"),
        turn_id=commit.value.turn_id,
        expected_turn_state_version=commit.value.state_version,
    )


def test_the_list_read_is_in_the_durable_order_not_the_insertion_order(
    db: sqlite3.Connection,
    fence: RuntimeEpochFence,
    cycle: CycleWorld,
    second_cycle: CycleWorld,
    teaching_store: SqliteTeachingStore,
) -> None:
    """``(created_at, moment_id)``: a row written later with an earlier stamp
    sorts earlier — the store's durable order, and the reason a
    time-classifying caller parses instants itself."""

    _open_moment(
        teaching_store,
        fence,
        cycle=cycle,
        moment_id="tm-later",
        created_at=DAY_TWO,
    )
    _close_moment(
        teaching_store, MomentId("tm-later"), abort_reason="POLICY_STOP"
    )
    _open_moment(
        teaching_store,
        fence,
        cycle=second_cycle,
        moment_id="tm-earlier",
        created_at=DAY_ONE,
    )
    read = teaching_store.list_moments_for_conversation(CONV)
    assert isinstance(read, Ok), read
    assert [str(moment.moment_id) for moment in read.value] == [
        "tm-earlier",
        "tm-later",
    ]


def test_the_list_read_of_an_unknown_conversation_is_empty(
    db: sqlite3.Connection,
    fence: RuntimeEpochFence,
    teaching_store: SqliteTeachingStore,
) -> None:
    read = teaching_store.list_moments_for_conversation(
        ConversationId("conv-p8-2-never")
    )
    assert isinstance(read, Ok)
    assert read.value == ()


def test_the_real_policy_read_face_has_the_ports_shape() -> None:
    """The port is shaped like ``UserConfigController.get_teaching_policy``
    (so an adapter is a forward, not a translation)."""

    signature = inspect.signature(UserConfigController.get_teaching_policy)
    assert list(signature.parameters) == ["self", "user_id"]
    hints = inspect.get_annotations(
        UserConfigController.get_teaching_policy, eval_str=True
    )
    assert hints["user_id"] is UserId
    assert hints["return"] == Result[TeachingPolicyProfile | None]


# -- ④ zero migrations, and no column anywhere else --------------------------


def test_no_migration_carries_the_view() -> None:
    """§5.2 labels the block ``Derived view``: the head is where it was and no
    migration mentions the view.

    P8-3 moved the head to 0016_planning_ledger (the PlanningLedger's tables,
    not this view), and this pin carries that head as **literals reconciled
    against the shared declarations**: the left-hand sides are
    ``tests.conftest``'s ``MIGRATION_IDS`` / ``SCHEMA_HEAD_FILE`` /
    ``SCHEMA_HEAD_VERSION`` (which
    ``tests/architecture/test_platform_db_infra.py`` pins against the real
    ``migrations/`` directory), and the right-hand sides are the literals this
    cut left behind — so a drift in either half is RED rather than a rubber
    stamp. The *claim* (this cut adds no table for the view) is unchanged, and
    the schema scan below is what holds it."""

    assert MIGRATION_IDS[-1] == "0016_planning_ledger"
    assert SCHEMA_HEAD_FILE == "0016_planning_ledger.sql"
    assert SCHEMA_HEAD_VERSION == "16"
    schema = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((REPO_ROOT / "migrations").glob("*.sql"))
    ).lower()
    assert "session_budget" not in schema


def test_the_view_is_registered_with_an_owner_and_the_views_version() -> None:
    """A derived view is still a canonical object, and the disposal's F3
    registers it beside its ``schedule_view`` sibling rather than leaving it
    unregistered: teaching-owned, and bound to the one version column §5.2's
    view block itself spells (``policy_version``)."""

    entry = CANONICAL_OBJECTS["session_budget_view"]
    assert entry.name == "SessionBudgetView"
    assert entry.owner == OWNER_TEACHING
    assert entry.schema is SessionBudgetView
    assert entry.version_field == "policy_version"


def test_the_planner_request_gained_no_field() -> None:
    """``session_budget_view`` travels in the §10 request already (P7-4's
    shape): this cut lands the view's production face, not a new column."""

    names = tuple(field.name for field in dataclasses.fields(PlanningRequest))
    assert names == (
        "decision_cycle_id",
        "learning_snapshot",
        "curriculum_candidate_view",
        "schedule_view",
        "goal_view",
        "teaching_policy_view",
        "context_opportunity_set",
        "planner_constraint_view",
        "session_budget_view",
        "user_intent_scope",
        "conversation_priority_view",
        "planning_ledger",
    )


def test_the_frontier_registration_still_names_the_view_and_still_says_why() -> None:
    """The P7-3 registration is **read**, not changed: ``cognitive
    feasibility``'s missing-authority entry names ``SessionBudgetView`` and its
    Revisit. This cut lands the view the entry was waiting for; the entry's own
    text is BF-02 semantics and stays untouched here (registered in the
    receipt and beside the view's derivation)."""

    registration = MISSING_FRONTIER_AUTHORITIES["cognitive feasibility"]
    assert "SessionBudgetView" in registration
    assert "Revisit" in registration
    assert "P6-1" in registration


def test_the_arrived_revisit_is_registered_beside_the_view() -> None:
    """The fact the book asks this cut to register: the frontier entry's
    revisit condition has fired for the view, and the entry stays untouched
    (answering it is a BF-02 semantics question for its own cut)."""

    module_doc = " ".join((budget.__doc__ or "").split())
    assert "MISSING_FRONTIER_AUTHORITIES" in module_doc
    assert "cognitive feasibility" in module_doc
    assert "this paragraph registers the fact" in module_doc
    assert "stay exactly as P7-3 wrote them" in module_doc
    # The quoted revisit is verbatim: the sentence this module quotes is the
    # one the frontier entry carries.
    quoted = (
        "Revisit: SessionBudgetView lands (or a cut lands any session-scope"
        " feasibility reading) — then the frontier question is re-asked with"
        " an authority behind it"
    )
    assert quoted in module_doc
    assert quoted in " ".join(
        MISSING_FRONTIER_AUTHORITIES["cognitive feasibility"].split()
    )


def test_the_budget_module_imports_cold() -> None:
    """One subprocess, the package as a consumer meets it — the P4-3
    cold-start rule for a new module this package's ``__init__`` imports."""

    program = "\n".join(
        [
            "import os, sys",
            "ROOT = os.environ['ROOT']",
            "sys.path[:0] = [os.path.join(ROOT, 'src'), ROOT]",
            "import elc.teaching.budget as budget",
            "import elc.teaching as teaching",
            "assert teaching.SessionBudgetView is budget.SessionBudgetView",
            "assert teaching.session_budget_view_of is budget.session_budget_view_of",
            "print('COLD-BUDGET', budget.COOLDOWN_WINDOW_SECONDS)",
        ]
    )
    process = subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPO_ROOT,
        env=dict(
            os.environ, PYTHONDONTWRITEBYTECODE="1", ROOT=str(REPO_ROOT)
        ),
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert process.returncode == 0, process.stderr
    assert "COLD-BUDGET 1800.0" in process.stdout
