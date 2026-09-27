"""D-6-a — the online chain, end to end, over the production path.

The D-5R suite injected the candidate (``candidate_supply=``); this one
injects nothing: the user's own turn text goes through the host's dispatch
face (``elc.detection.dispatch`` over the process-level pilot registry), the
generators run over the real ports, and the planner's CURRENT_USER_ERROR
candidate walks the whole authorization chain the D-5R safety closure built
(EV eligibility, the budget view, the stage × mode gate).

The one production-shaped setup step: the §5.2 row is written through the
host's own ``SchedulerController.recompute_schedule_item`` (a
``NOT_SCHEDULED`` row — "asked and answered", BF-02 §5's distinction
between "no review debt" and "never asked"; without it the generator refuses
the candidate at ``SCHEDULE_ROW``). No seam is touched: everything here is a
face the shipped assembly exposes.

Pinned here:

1. the positive chain — an error in the user's text becomes a durable
   AUTOMATIC moment the Gate ALLOWed, with the matched entity as the focus;
2. the contrast — a clean text is an ordinary COMPLETED turn with no moment
   and no gate row;
3. the fail-safe — a detector face that raises never breaks the user's turn
   (the wiring degrades to no observation, exactly like every other
   optional leg).
"""

from __future__ import annotations

import uuid
from dataclasses import replace
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
from elc.platform.types import (
    ClientMessageId,
    ConversationId,
    EvidenceModality,
    InputId,
    InteractionChannel,
    Ok,
    TargetId,
)
from elc.runtime.types import InputEnvelope, TurnStatus
from elc.teaching.rollout import RolloutStage

CONV = ConversationId("d6a-conv")
REPLY = "d6a reply"
ERROR_TEXT = "Any way, let's continue with the plan."
CLEAN_TEXT = "The meeting starts at nine."
EV_TARGET = "res-discourse-anyway"


@pytest.fixture(scope="module")
def pilot_content_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("d6a-pilot") / "content.db"
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
            input_id=InputId(f"d6a-{suffix}"),
            client_message_id=ClientMessageId(f"d6a-msg-{suffix}"),
            conversation_id=str(CONV),
            persona_id=None,
            scene_id=None,
            interaction_channel=InteractionChannel.TEXT,
            raw_payload=text,
            received_at=datetime.now(tz=UTC).isoformat(),
        ),
        raw_content=text,
        runtime_version="runtime-d6a",
    )


def online_host(app_db: Path, content_db: Path) -> Host:
    """The production path: no candidate supply, stage declared explicitly."""

    return open_host(
        app_db,
        provider=ScriptedPersonaProvider(script=(ProviderOutput(text=REPLY),)),
        content_db_path=content_db,
        rollout_stage=RolloutStage.STUDY_FIRST,
    )


def seed(host: Host) -> None:
    """The §5.1 policy + goal portfolio, then the §5.2 NOT_SCHEDULED row —
    all through the host's own controllers, never around them."""

    from elc.platform.types import GoalId, GoalModality, GoalVersion, PolicyVersion
    from elc.user_config.types import (
        LearningGoal,
        LearningGoalPortfolio,
        TeachingFrequency,
        TeachingPolicyProfile,
    )

    assert host.user_id is not None
    written = host.user_config.upsert_teaching_policy(
        TeachingPolicyProfile(
            teaching_policy_profile_id=host.user_id,
            policy_version=PolicyVersion("pv-d6a"),
            teaching_frequency=TeachingFrequency.BALANCED,
        )
    )
    assert isinstance(written, Ok), written
    portfolio = host.user_config.upsert_goal_portfolio(
        LearningGoalPortfolio(
            goal_portfolio_id=host.user_id,
            goal_version=GoalVersion("gv-d6a"),
            goals=(
                LearningGoal(
                    goal_id=GoalId("goal-d6a"),
                    goal_modality=GoalModality.SPEAKING,
                    description="a long-term goal",
                ),
            ),
            modality_weights={GoalModality.SPEAKING: 1.0},
            assessment_targets=(),
            effective_from=datetime.now(tz=UTC).isoformat(),
        )
    )
    assert isinstance(portfolio, Ok), portfolio
    row = host.curriculum.get_target(TargetId(EV_TARGET))
    assert isinstance(row, Ok), row
    scheduled = host.scheduler.recompute_schedule_item(
        row.value.target_type,
        TargetId(EV_TARGET),
        EvidenceModality(row.value.evidence_modality),
        datetime.now(tz=UTC).isoformat(),
    )
    assert isinstance(scheduled, Ok), scheduled


def test_the_online_chain_opens_the_moment_from_the_user_text(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    host = online_host(tmp_path / "app.db", pilot_content_db)
    try:
        # the producer is really wired (and really reads the text)
        assert host.automatic is not None
        assert host.automatic.error_detectors is not None
        assert host.automatic.error_detectors.detect_current_user_errors(
            ERROR_TEXT
        ) == (EV_TARGET,)
        assert isinstance(host.open_conversation(CONV), Ok)
        seed(host)
        result = host.coordinator.begin_turn(command(ERROR_TEXT))
        assert isinstance(result, Ok), result
        assert result.value.turn_status is TurnStatus.COMPLETED
        moment = host.db.execute(
            "SELECT lifecycle_state, source, focus_target FROM teaching_moment"
        ).fetchone()
        assert moment is not None
        assert moment[0] == "AWAITING_USER"
        assert moment[1] == "AUTOMATIC"
        assert EV_TARGET in str(moment[2])
        gate = host.db.execute(
            "SELECT context, decision FROM gate_decision"
        ).fetchone()
        assert gate == ("OPEN", "ALLOW")
        action = host.db.execute(
            "SELECT action_id FROM generation_action_intent"
        ).fetchone()
        assert action is not None and str(action[0]).endswith("automatic-open")
    finally:
        host.close()


def test_a_clean_turn_is_an_ordinary_completed_turn(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    host = online_host(tmp_path / "app.db", pilot_content_db)
    try:
        assert isinstance(host.open_conversation(CONV), Ok)
        seed(host)
        result = host.coordinator.begin_turn(command(CLEAN_TEXT))
        assert isinstance(result, Ok), result
        assert result.value.turn_status is TurnStatus.COMPLETED
        assert (
            host.db.execute("SELECT COUNT(*) FROM teaching_moment").fetchone()[0]
            == 0
        )
        assert (
            host.db.execute("SELECT COUNT(*) FROM gate_decision").fetchone()[0]
            == 0
        )
    finally:
        host.close()


class _RaisingDetectors:
    """A face that breaks — the shape the fail-safe must survive."""

    def detect_current_user_errors(self, text: str) -> tuple[str, ...]:
        raise RuntimeError("the detector face exploded (injected)")


def test_a_raising_detector_face_never_breaks_the_user_turn(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    host = online_host(tmp_path / "app.db", pilot_content_db)
    try:
        assert isinstance(host.open_conversation(CONV), Ok)
        seed(host)
        assert host.automatic is not None
        host.coordinator._automatic = replace(
            host.automatic, error_detectors=_RaisingDetectors()
        )
        result = host.coordinator.begin_turn(command(ERROR_TEXT))
        assert isinstance(result, Ok), result
        assert result.value.turn_status is TurnStatus.COMPLETED
        assert (
            host.db.execute("SELECT COUNT(*) FROM teaching_moment").fetchone()[0]
            == 0
        )
        # the same turn on the unmutated wiring opens — the refusal above is
        # the fail-safe's, not the chain being broken
        host.coordinator._automatic = host.automatic
        result = host.coordinator.begin_turn(command(ERROR_TEXT))
        assert isinstance(result, Ok), result
        assert (
            host.db.execute("SELECT COUNT(*) FROM teaching_moment").fetchone()[0]
            == 1
        )
    finally:
        host.close()
