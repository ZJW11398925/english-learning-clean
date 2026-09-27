"""D-5R — the full-chain host, end to end, over the safety closure.

The one test that answers external review round 5's question with a real
process: a host assembled by ``open_host`` (the composition root), a pilot
``content.db``, an explicitly declared ``STUDY_FIRST`` stage, a seeded §5.1
policy row, and one CURRENT_USER_ERROR candidate handed to the wiring's own
``candidate_supply`` seam — the same injection point the P8-4 suite uses,
reached through the shipped assembly instead of around it.

Pinned here:

1. the session-budget leg the host wires reads for real (seeded row ⇒ the
   view answers that row's version; no row ⇒ a view whose
   ``policy_version`` is ``None`` — a value, not the wired-face refusal);
2. the positive chain: an EV target's CURRENT_USER_ERROR candidate walks
   the whole leg — decision cycle, planner half, the two authorization
   refusals (passed, not fired), the Gate's ALLOW, the CP2 five facts, and
   a real delivery;
3. the negative chain: the same candidate on a target that is R4 but only
   ``EDITOR_REVIEWED`` in this artifact is refused at the authorization
   point with ``TARGET_NOT_EXECUTABLY_VERIFIED`` — no moment, no lock, no
   action (the runtime per-target leg of the fifth gate leg, D-5R).
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from elc.content.build import build_content_db
from elc.conversation.types import CommitUserTurn
from elc.detection import DetectorRegistry
from elc.detection.pilot import PILOT_VERSION, register_pilot
from elc.host import Host, open_host
from elc.persona.provider import ScriptedPersonaProvider
from elc.persona.types import ProviderOutput
from elc.planner.kernel import ReadinessLevel
from elc.platform.types import (
    ClientMessageId,
    ConversationId,
    InputId,
    InteractionChannel,
    Ok,
    TargetId,
)
from elc.runtime.types import InputEnvelope, TurnStatus
from elc.teaching.rollout import RolloutStage
from tests.phase7.conftest import DAY_TWO, kernel_row, proposal
from tests.phase8.conftest import supply_of

CONV = ConversationId("d5r-conv")
REPLY = "d5r reply"

#: The pilot-verified target the positive chain runs on (one of the D-3
#: twelve, so the pilot artifact's provenance table answers
#: EXECUTABLY_VERIFIED for it).
EV_TARGET = TargetId("res-pragmatic-no-way")

#: An R4 target the pilot build holds at EDITOR_REVIEWED (C1's first R4,
#: never in the pilot twelve) — the exact shape the runtime eligibility leg
#: refuses, and the release-level corpus gate counts among the blocked.
NOT_EV_TARGET = TargetId("res-colloc-make-a-decision")


@pytest.fixture(scope="module")
def pilot_content_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One pilot content.db: twelve EXECUTABLY_VERIFIED rows + its profile."""

    path = tmp_path_factory.mktemp("d5r-pilot") / "content.db"
    registry = DetectorRegistry()
    register_pilot(registry)
    build_content_db(
        path,
        detector_registry=registry,
        verification_pilot_version=PILOT_VERSION,
    )
    return path


def command(text: str) -> CommitUserTurn:
    suffix = uuid.uuid4().hex
    return CommitUserTurn(
        conversation_id=CONV,
        envelope=InputEnvelope(
            input_id=InputId(f"d5r-{suffix}"),
            client_message_id=ClientMessageId(f"d5r-msg-{suffix}"),
            conversation_id=str(CONV),
            persona_id=None,
            scene_id=None,
            interaction_channel=InteractionChannel.TEXT,
            raw_payload=text,
            received_at=datetime.now(tz=UTC).isoformat(),
        ),
        raw_content=text,
        runtime_version="runtime-d5r",
    )


def scripted(text: str = REPLY) -> ScriptedPersonaProvider:
    return ScriptedPersonaProvider(script=(ProviderOutput(text=text),))


def full(
    app_db: Path, content_db: Path, *, candidate_target: object, **kwargs: object
) -> Host:
    """One full-chain host over the pilot artifact, with the CURRENT_USER_ERROR
    candidate already handed to the wiring's supply seam."""

    supplied = supply_of(
        proposal(
            "cand-d5r-e2e",
            focus_target=str(candidate_target),
            origins=("CURRENT_USER_ERROR",),
            content_readiness=ReadinessLevel.R4_DETECTION_READY,
            schedule_row=kernel_row(urgency=0.75),
        )
    )
    return open_host(
        app_db,
        provider=scripted(),  # type: ignore[arg-type]
        content_db_path=content_db,
        rollout_stage=RolloutStage.STUDY_FIRST,
        candidate_supply=supplied,
        **kwargs,
    )


def seed_policy(host: Host) -> None:
    """The §5.1 rows, written through the host's own controller face (the
    D-5R policy adapter is what makes the policy row readable by the budget
    view; the goal portfolio is the kernel's GOAL_PORTFOLIO authority)."""

    from elc.platform.types import (
        GoalId,
        GoalModality,
        GoalVersion,
        PolicyVersion,
    )
    from elc.user_config.types import (
        LearningGoal,
        LearningGoalPortfolio,
        TeachingFrequency,
        TeachingPolicyProfile,
    )

    assert host.user_config is not None
    written = host.user_config.upsert_teaching_policy(
        TeachingPolicyProfile(
            teaching_policy_profile_id=host.user_id,
            policy_version=PolicyVersion("pv-d5r-e2e"),
            teaching_frequency=TeachingFrequency.BALANCED,
        )
    )
    assert isinstance(written, Ok), written
    portfolio = host.user_config.upsert_goal_portfolio(
        LearningGoalPortfolio(
            goal_portfolio_id=host.user_id,
            goal_version=GoalVersion("gv-d5r-e2e"),
            goals=(
                LearningGoal(
                    goal_id=GoalId("goal-d5r"),
                    goal_modality=GoalModality.SPEAKING,
                    description="a long-term goal",
                ),
            ),
            modality_weights={GoalModality.SPEAKING: 1.0},
            assessment_targets=(),
            effective_from=DAY_TWO,
        )
    )
    assert isinstance(portfolio, Ok), portfolio


# ---------------------------------------------------------------------------
# 1. the budget leg reads for real
# ---------------------------------------------------------------------------


def test_the_full_chain_budget_view_reads_a_seeded_policy_row(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    host = full(
        tmp_path / "app.db", pilot_content_db, candidate_target=EV_TARGET
    )
    try:
        seed_policy(host)
        assert host.teaching is not None
        view = host.teaching.get_session_budget_view(
            CONV, DAY_TWO  # type: ignore[arg-type]
        )
        assert isinstance(view, Ok), view
        assert view.value.policy_version == "pv-d5r-e2e"
        assert view.value.automatic_teaching_used == 0
    finally:
        host.close()


def test_the_wired_view_answers_none_version_without_a_row(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    host = full(
        tmp_path / "app.db", pilot_content_db, candidate_target=EV_TARGET
    )
    try:
        assert host.teaching is not None
        view = host.teaching.get_session_budget_view(
            CONV, DAY_TWO  # type: ignore[arg-type]
        )
        assert isinstance(view, Ok), view
        assert view.value.policy_version is None
    finally:
        host.close()


# ---------------------------------------------------------------------------
# 2. the positive chain: EV target's candidate opens and delivers
# ---------------------------------------------------------------------------


def test_the_positive_chain_opens_and_delivers(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    host = full(
        tmp_path / "app.db", pilot_content_db, candidate_target=EV_TARGET
    )
    try:
        assert isinstance(host.open_conversation(CONV), Ok)
        seed_policy(host)
        result = host.coordinator.begin_turn(command("Any way, let's continue."))
        assert isinstance(result, Ok), result
        assert result.value.turn_status is TurnStatus.COMPLETED
        # the automatic opening: one moment, live and awaiting the user
        assert count(host.db, "teaching_moment") == 1
        moment = host.db.execute(
            "SELECT lifecycle_state, source, focus_target FROM teaching_moment"
        ).fetchone()
        assert moment[0] == "AWAITING_USER"
        assert moment[1] == "AUTOMATIC"
        assert str(EV_TARGET) in str(moment[2])
        # the Gate ALLOWed the OPEN
        gate = host.db.execute(
            "SELECT context, decision FROM gate_decision"
        ).fetchone()
        assert gate == ("OPEN", "ALLOW")
        # and the delivery is real: the opening action went out on this turn
        action = host.db.execute(
            "SELECT action_id FROM generation_action_intent"
        ).fetchone()
        assert str(action[0]).endswith("automatic-open")
        assert count(host.db, "assistant_turn") == 1
    finally:
        host.close()


def test_the_positive_chain_stamps_the_cycle_and_the_lock(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    host = full(
        tmp_path / "app.db", pilot_content_db, candidate_target=EV_TARGET
    )
    try:
        assert isinstance(host.open_conversation(CONV), Ok)
        seed_policy(host)
        opened = host.coordinator.begin_turn(command("Any way, let's continue."))
        assert isinstance(opened, Ok), opened
        # the budget view the authorization read left its trace: the cycle
        # binds the policy version the seeded row carries
        cycle = host.db.execute(
            "SELECT policy_version FROM decision_cycle"
        ).fetchone()
        assert cycle[0] == "pv-d5r-e2e"
        # and the CP2 lock is held by the moment it opened
        assert count(host.db, "active_teaching_lock") == 1
    finally:
        host.close()


# ---------------------------------------------------------------------------
# 3. the negative chain: R4-but-not-EV is refused at the authorization point
# ---------------------------------------------------------------------------


def test_a_not_verifiably_executable_target_is_refused_end_to_end(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    host = full(
        tmp_path / "app.db", pilot_content_db, candidate_target=NOT_EV_TARGET
    )
    try:
        assert isinstance(host.open_conversation(CONV), Ok)
        seed_policy(host)
        result = host.coordinator.begin_turn(command("Any way, let's continue."))
        assert isinstance(result, Ok), result
        # the turn itself completes as an ordinary one
        assert result.value.turn_status is TurnStatus.COMPLETED
        # and the OPEN was refused durably, at the authorization point
        gate = host.db.execute(
            "SELECT context, decision, reason_codes FROM gate_decision"
        ).fetchone()
        assert gate is not None
        assert gate[0] == "OPEN" and gate[1] == "DENY"
        assert "TARGET_NOT_EXECUTABLY_VERIFIED" in str(gate[2])
        assert count(host.db, "teaching_moment") == 0
        assert count(host.db, "active_teaching_lock") == 0
        # the refusal is the stage refusal's shape: status SUCCEEDED beside
        # the DENY, never a degraded laundering of the fact
        status = host.db.execute(
            "SELECT status FROM gate_execution_status"
        ).fetchone()
        assert status is not None and status[0] == "SUCCEEDED"
    finally:
        host.close()


def count(db: sqlite3.Connection, table: str) -> int:
    return int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
