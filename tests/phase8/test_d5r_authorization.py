"""D-5R — the automatic OPEN's two authorization refusals, at the unit.

The unit (:func:`elc.runtime.automatic_teaching.decide_automatic_teaching`)
is driven over the real world exactly as its P8-1 suite drives it: a real
conversation → CP0 turn → decision cycle, P7-0's real record store, P7-4's
real kernel run for the SELECT answer, and the real ``SqliteTeachingStore``
behind the real ``TeachingController``. Pinned here:

1. the session-budget leg is **mandatory** at the authorization point: a
   budget view that could not be read (``Err`` / ``DEPENDENCY_UNAVAILABLE``
   / absent — all one shape to the caller) refuses the OPEN with
   ``AUTO_SESSION_BUDGET_UNREADABLE``, recorded in the stage refusal's
   durable shape (status SUCCEEDED + GateDecision DENY), and a re-entry
   replays that DENY instead of re-deciding;
2. the CURRENT_USER_ERROR candidate's target must reach
   ``EXECUTABLE_VERIFICATION_FLOOR`` on the wiring's provenance mapping —
   positive (EV target opens), and the three refusals (below-floor level,
   target absent from the mapping, face missing entirely), plus the
   unknown-word fail-closed reading and the never-gated other sources;
3. the D-5R floor mirror answers what ``elc.teaching.rollout``'s private
   fifth-leg helper answers, level for level (the restate-and-pin rule);
4. the composition root's policy adapter gives the full chain a budget view
   that really reads — seeded row ⇒ ``policy_version``, no row ⇒ a view
   with ``policy_version=None`` — while the bare controller's documented
   refusal stays (a read-face fact, unchanged);
5. the wiring forwards the three authorization facts to the unit (a
   normalized-source pin, the F5-family limitation stated on the pin).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from elc.content.types import PROVENANCE_LEVELS
from elc.planner.shadow import run_shadow
from elc.platform.db.decision_cycle_store import SqliteDecisionCycleStore
from elc.platform.db.planner_store import SqlitePlannerRecordStore
from elc.platform.types import (
    DecisionCycleId,
    DomainErrorCode,
    Err,
    Ok,
    PolicyVersion,
)
from elc.runtime import automatic_teaching, automatic_turn
from elc.runtime.automatic_teaching import (
    AUTO_SESSION_BUDGET_UNREADABLE,
    PROVENANCE_FACE_MISSING,
    TARGET_NOT_EXECUTABLY_VERIFIED,
    AutomaticTeachingTurn,
    TeachingControlFacts,
    _provenance_reaches_floor,
    automatic_gate_decision_id,
    automatic_moment_id,
    decide_automatic_teaching,
)
from elc.teaching.controller import TeachingController
from elc.teaching.rollout import EXECUTABLE_VERIFICATION_FLOOR
from elc.teaching.store import SqliteTeachingStore
from elc.teaching.types import (
    MomentSource,
    MomentState,
    PresentationPhase,
    TeachingMomentRecord,
    TeachingSupportLevel,
    TeachingTargetRef,
)
from elc.user_config.controller import UserConfigController
from elc.user_config.store import SqliteUserConfigStore
from elc.user_config.types import (
    TeachingFrequency,
    TeachingPolicyProfile,
)
from tests.phase7.conftest import DAY_ONE, TARGET_ID, WATERMARK, proposal
from tests.phase8.conftest import CONV, request_of, supply_of

POLICY_VERSION = "pv-d5r"


@pytest.fixture()
def teaching_controller(
    db: sqlite3.Connection, fence
) -> TeachingController:
    """The bare controller (no policy source) over the real teaching store —
    the CP2 commit face the unit's refusals and ALLOW both write through."""

    return TeachingController(SqliteTeachingStore(db, fence))


# -- the world (the P8-1 suite's shape, owned here) --------------------------


def _moment_template(turn_id) -> TeachingMomentRecord:
    """The §15 template of the moment an ALLOW would open (the unit's own
    refusal checks the derived fields, so the template arrives in the
    derived-field-free shape the wiring builds)."""

    return TeachingMomentRecord(
        moment_id=automatic_moment_id(turn_id),
        conversation_id=CONV,
        persona_id=None,
        source=MomentSource.AUTOMATIC,
        decision_cycle_id=DecisionCycleId("dc-unused"),
        candidate_id="cand-unused",
        gate_decision_id=automatic_gate_decision_id(turn_id),
        focus_target=TeachingTargetRef("RESOURCE", str(TARGET_ID)),
        supporting_targets=(),
        target_mode="RESOURCE_PRACTICE",
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
    )


def _cycle_record(db: sqlite3.Connection, fence, cycle) -> object:
    read = SqliteDecisionCycleStore(
        db, fence  # type: ignore[arg-type]
    ).get_decision_cycle(cycle.decision_cycle_id)
    assert isinstance(read, Ok), read
    assert read.value is not None
    return read.value


def _select_outcome(cycle):
    """A real kernel run over a one-proposal supply: the SELECT answer the
    unit's post-planner refusals are reached through."""

    return run_shadow(
        request_of(decision_cycle_id=cycle.decision_cycle_id),
        supply=supply_of(proposal("cand-d5r")),
        current_learning_watermark=WATERMARK,
    ).outcome


def _decide(
    cycle,
    db: sqlite3.Connection,
    fence,
    planner_store: SqlitePlannerRecordStore,
    teaching: TeachingController,
    *,
    session_budget_readable: bool = True,
    candidate_provenance_gated: bool = False,
    provenance: dict[str, str] | None = None,
):
    record = _cycle_record(db, fence, cycle)
    return decide_automatic_teaching(
        turn=AutomaticTeachingTurn(
            turn_id=record.turn_id,  # type: ignore[attr-defined]
            conversation_id=CONV,
            persona_id=None,
            cycle=record,  # type: ignore[arg-type]
            moment=_moment_template(record.turn_id),  # type: ignore[attr-defined]
            owner_epoch=1,
        ),
        outcome=_select_outcome(cycle),
        controls=TeachingControlFacts(),
        planner_store=planner_store,
        teaching=teaching,
        session_budget_readable=session_budget_readable,
        candidate_provenance_gated=candidate_provenance_gated,
        provenance=provenance,
    )


_TEACHING_TABLES = (
    "teaching_moment",
    "active_teaching_lock",
    "generation_action_intent",
)


def _counts(db: sqlite3.Connection) -> dict[str, int]:
    return {
        table: int(
            db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        )
        for table in _TEACHING_TABLES
    }


def _gate_rows(db: sqlite3.Connection) -> tuple[tuple[object, ...], ...]:
    return tuple(
        tuple(row)
        for row in db.execute(
            "SELECT context, decision, reason_codes FROM gate_decision"
        )
    )


def _policy_wired_controller(
    db: sqlite3.Connection, fence
) -> tuple[TeachingController, UserConfigController]:
    """The composition root's adapter shape, over the real stores: the
    full chain's ``TeachingController(store, policy=_UserConfigPolicySource(
    user_config, user_id))`` — the adapter is host.py's own private class,
    imported here by name and reconstructed over the same two faces, so
    this module pins the local reconstruction against the real one."""

    from elc.host import LOCAL_V1_USER_ID, _UserConfigPolicySource

    user_config = UserConfigController(SqliteUserConfigStore(db, fence))
    teaching = TeachingController(
        SqliteTeachingStore(db, fence),
        policy=_UserConfigPolicySource(user_config, LOCAL_V1_USER_ID),
    )
    return teaching, user_config


# ---------------------------------------------------------------------------
# 1. the budget leg is mandatory at the authorization point
# ---------------------------------------------------------------------------


def test_a_readable_budget_still_opens(
    db, fence, cycle, planner_store, teaching_controller
) -> None:
    """The control group: with the budget leg readable, the same SELECT run
    ALLOWs exactly as before D-5R — the refusal fires only where it can
    change an outcome."""

    decided = _decide(
        cycle, db, fence, planner_store, teaching_controller
    )
    assert isinstance(decided, Ok), decided
    assert decided.value.normal_persona_generation is False
    assert decided.value.gate_verdict is not None
    assert decided.value.gate_verdict.decision == "ALLOW"


def test_an_unreadable_budget_refuses_the_automatic_open(
    db, fence, cycle, planner_store, teaching_controller
) -> None:
    """``session_budget_readable=False`` (the wiring's budget leg came back
    Err / DEPENDENCY_UNAVAILABLE / absent) refuses the OPEN: a durable DENY
    in the stage refusal's shape, the cut's own reason word, and an ordinary
    turn — never a moment opened on a budget nobody could read."""

    decided = _decide(
        cycle,
        db,
        fence,
        planner_store,
        teaching_controller,
        session_budget_readable=False,
    )
    assert isinstance(decided, Ok), decided
    result = decided.value
    assert result.normal_persona_generation is True
    assert result.moment_id is None and result.action_id is None
    assert result.gate_verdict is not None
    assert result.gate_verdict.decision == "DENY"
    assert result.gate_verdict.primary_reason == AUTO_SESSION_BUDGET_UNREADABLE
    assert result.gate_verdict.reasons == (AUTO_SESSION_BUDGET_UNREADABLE,)
    # the durable shape: one DENY decision + its SUCCEEDED status, no moment
    rows = _gate_rows(db)
    assert len(rows) == 1
    assert rows[0][0] == "OPEN" and rows[0][1] == "DENY"
    assert AUTO_SESSION_BUDGET_UNREADABLE in str(rows[0][2])
    assert _counts(db) == dict.fromkeys(_TEACHING_TABLES, 0)


def test_an_unreadable_budget_denial_is_replayed_not_redecided(
    db, fence, cycle, planner_store, teaching_controller
) -> None:
    """The recorded refusal is a durable fact: a re-entry whose budget leg
    now reads fine replays the DENY (the unit never writes a second,
    contradicting Gate fact under one cycle)."""

    first = _decide(
        cycle,
        db,
        fence,
        planner_store,
        teaching_controller,
        session_budget_readable=False,
    )
    assert isinstance(first, Ok), first
    replay = _decide(
        cycle, db, fence, planner_store, teaching_controller
    )
    assert isinstance(replay, Ok), replay
    assert replay.value.gate_verdict is not None
    assert replay.value.gate_verdict.decision == "DENY"
    assert replay.value.gate_verdict.primary_reason == (
        AUTO_SESSION_BUDGET_UNREADABLE
    )
    assert len(_gate_rows(db)) == 1


# ---------------------------------------------------------------------------
# 2. the per-target EV eligibility of CURRENT_USER_ERROR candidates
# ---------------------------------------------------------------------------


def _gated(**overrides: object) -> dict[str, object]:
    facts: dict[str, object] = {
        "candidate_provenance_gated": True,
        "provenance": {str(TARGET_ID): "EXECUTABLY_VERIFIED"},
    }
    facts.update(overrides)
    return facts


def test_a_verified_target_serves_its_current_user_error_candidate(
    db, fence, cycle, planner_store, teaching_controller
) -> None:
    """The positive leg: a CURRENT_USER_ERROR candidate whose target reached
    EXECUTABLY_VERIFIED on the wiring's mapping opens exactly as an
    ungated one does."""

    decided = _decide(
        cycle, db, fence, planner_store, teaching_controller, **_gated()
    )
    assert isinstance(decided, Ok), decided
    assert decided.value.normal_persona_generation is False
    assert decided.value.gate_verdict is not None
    assert decided.value.gate_verdict.decision == "ALLOW"


def test_a_below_floor_target_refuses_its_candidate(
    db, fence, cycle, planner_store, teaching_controller
) -> None:
    """An R4 target whose provenance sits at EDITOR_REVIEWED — the exact
    EXT-C3-03 shape, now refused at the only place an OPEN can be
    authorized."""

    decided = _decide(
        cycle,
        db,
        fence,
        planner_store,
        teaching_controller,
        **_gated(provenance={str(TARGET_ID): "EDITOR_REVIEWED"}),
    )
    assert isinstance(decided, Ok), decided
    assert decided.value.normal_persona_generation is True
    assert decided.value.gate_verdict is not None
    assert (
        decided.value.gate_verdict.primary_reason
        == TARGET_NOT_EXECUTABLY_VERIFIED
    )
    assert _counts(db)["teaching_moment"] == 0


def test_a_target_outside_the_mapping_refuses_its_candidate(
    db, fence, cycle, planner_store, teaching_controller
) -> None:
    """A mapping that does not name the target establishes nothing: no row
    is not a pass."""

    decided = _decide(
        cycle,
        db,
        fence,
        planner_store,
        teaching_controller,
        **_gated(provenance={"res-some-other-target": "EXECUTABLY_VERIFIED"}),
    )
    assert isinstance(decided, Ok), decided
    assert decided.value.gate_verdict is not None
    assert (
        decided.value.gate_verdict.primary_reason
        == TARGET_NOT_EXECUTABLY_VERIFIED
    )


def test_a_missing_provenance_face_refuses_its_candidate(
    db, fence, cycle, planner_store, teaching_controller
) -> None:
    """``provenance=None`` (no face wired) is its own refusal word — the
    repair is wiring the face, not fixing a level — and no moment opens."""

    decided = _decide(
        cycle,
        db,
        fence,
        planner_store,
        teaching_controller,
        candidate_provenance_gated=True,
        provenance=None,
    )
    assert isinstance(decided, Ok), decided
    assert decided.value.gate_verdict is not None
    assert decided.value.gate_verdict.primary_reason == PROVENANCE_FACE_MISSING
    assert _counts(db)["teaching_moment"] == 0


def test_an_unknown_provenance_word_refuses_its_candidate(
    db, fence, cycle, planner_store, teaching_controller
) -> None:
    """A word the provenance ladder does not carry is refused, not guessed
    (the repository's unknown-word rule, at the runtime leg)."""

    decided = _decide(
        cycle,
        db,
        fence,
        planner_store,
        teaching_controller,
        **_gated(provenance={str(TARGET_ID): "SURE_LOOKS_VERIFIED"}),
    )
    assert isinstance(decided, Ok), decided
    assert decided.value.gate_verdict is not None
    assert (
        decided.value.gate_verdict.primary_reason
        == TARGET_NOT_EXECUTABLY_VERIFIED
    )


def test_other_sources_are_never_provenance_gated(
    db, fence, cycle, planner_store, teaching_controller
) -> None:
    """The eligibility leg keys on the candidate's §6 source and nothing
    else: a non-CURRENT_USER_ERROR candidate runs ungated even when no
    provenance face exists at all (the D-4 shape: only the
    CURRENT_USER_ERROR row reads provenance)."""

    decided = _decide(
        cycle,
        db,
        fence,
        planner_store,
        teaching_controller,
        candidate_provenance_gated=False,
        provenance=None,
    )
    assert isinstance(decided, Ok), decided
    assert decided.value.normal_persona_generation is False
    assert decided.value.gate_verdict is not None
    assert decided.value.gate_verdict.decision == "ALLOW"


# ---------------------------------------------------------------------------
# 3. the floor mirror answers what the release-level helper answers
# ---------------------------------------------------------------------------


def test_the_runtime_floor_mirror_matches_the_release_level_helper() -> None:
    """``_provenance_reaches_floor`` restated
    ``elc.teaching.rollout._provenance_reaches_executable`` rather than
    importing it (that module's private) — the restate-and-pin rule: the
    two answer identically for every ladder word, ``None``, and a word the
    ladder does not carry."""

    from elc.teaching.rollout import _provenance_reaches_executable

    words: list[str | None] = [*PROVENANCE_LEVELS, None, "NOT_A_LEVEL"]
    for word in words:
        assert _provenance_reaches_floor(word) == (
            _provenance_reaches_executable(word)
        ), word
    # and the floor is the word D-4 registered
    assert EXECUTABLE_VERIFICATION_FLOOR == "EXECUTABLY_VERIFIED"


# ---------------------------------------------------------------------------
# 4. the composition root's policy adapter gives the budget view a voice
# ---------------------------------------------------------------------------


def _seed_policy(user_config: UserConfigController) -> Ok:
    written = user_config.upsert_teaching_policy(
        TeachingPolicyProfile(
            teaching_policy_profile_id="user-local-v1",
            policy_version=PolicyVersion(POLICY_VERSION),
            teaching_frequency=TeachingFrequency.BALANCED,
        )
    )
    assert isinstance(written, Ok), written
    return written


def test_the_wired_controller_answers_a_real_budget_view(
    db, fence
) -> None:
    """A. The full chain's budget leg: policy wired, row seeded ⇒ the view
    answers with that row's version — the fact EXT-D5-01 said the full host
    could never produce."""

    teaching, user_config = _policy_wired_controller(db, fence)
    _seed_policy(user_config)
    view = teaching.get_session_budget_view(CONV, DAY_ONE)
    assert isinstance(view, Ok), view
    assert view.value.policy_version == POLICY_VERSION
    assert view.value.automatic_teaching_used == 0
    assert view.value.automatic_teaching_remaining is None


def test_the_wired_controller_answers_a_view_without_a_policy_row(
    db, fence
) -> None:
    """Wired but never written: "no policy is configured" is a view with
    ``policy_version=None`` — a value, not the wired-face refusal."""

    teaching, _ = _policy_wired_controller(db, fence)
    view = teaching.get_session_budget_view(CONV, DAY_ONE)
    assert isinstance(view, Ok), view
    assert view.value.policy_version is None


def test_the_bare_controller_still_refuses_the_view(db, fence) -> None:
    """The read-face fact D-5R did not touch: a controller constructed
    without a policy source refuses the view with
    ``DEPENDENCY_UNAVAILABLE`` — "no policy read face was wired" stays a
    different fact from "no policy is configured"."""

    teaching = TeachingController(SqliteTeachingStore(db, fence))
    view = teaching.get_session_budget_view(CONV, DAY_ONE)
    assert isinstance(view, Err), view
    assert view.error.code is DomainErrorCode.DEPENDENCY_UNAVAILABLE


# ---------------------------------------------------------------------------
# 5. the wiring forwards the three authorization facts
# ---------------------------------------------------------------------------


def test_the_wiring_forwards_the_authorization_facts() -> None:
    """``decide_automatic_turn`` derives and passes the three facts the
    unit's refusals read: budget readability off the plan's own view, the
    gated-source test off the selected proposal's origins, and the wiring's
    provenance mapping verbatim. Pinned as a normalized-source scan (the
    F5-family limitation ``test_p8_4_honesty`` states for its own
    forwarding pin: a rewrite through an alias or a ``**kwargs`` splat
    would evade the scan while keeping the behaviour)."""

    source = Path(str(automatic_turn.__file__)).read_text(encoding="utf-8")
    normalized = " ".join(source.split())
    assert (
        "session_budget_readable=isinstance( plan.session_budget_view,"
        " SessionBudgetView )" in normalized
    )
    assert (
        'candidate_provenance_gated=( plan.selected is not None and'
        " \"CURRENT_USER_ERROR\" in plan.selected.origins )" in normalized
    )
    assert "provenance=wiring.provenance" in normalized


# ---------------------------------------------------------------------------
# 6. the three refusal words are their own words (D-5R review LOW-1)
# ---------------------------------------------------------------------------


def test_the_refusal_words_are_literally_themselves() -> None:
    """The three D-5R refusals must not be silently aliased onto a Gate
    frozen word: "budget unreadable" reported as "budget exhausted" (or
    "not verified" as "teaching disabled") would be a lie with a durable
    row behind it, and every other pin here reads the Python symbol —
    which an alias assignment keeps green. The words are pinned by value
    (the review's m9 form: re-point one constant at a Gate word ⇒ this
    goes red)."""

    assert automatic_teaching.AUTO_SESSION_BUDGET_UNREADABLE == (
        "AUTO_SESSION_BUDGET_UNREADABLE"
    )
    assert automatic_teaching.TARGET_NOT_EXECUTABLY_VERIFIED == (
        "TARGET_NOT_EXECUTABLY_VERIFIED"
    )
    assert automatic_teaching.PROVENANCE_FACE_MISSING == (
        "PROVENANCE_FACE_MISSING"
    )
