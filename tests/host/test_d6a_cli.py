"""D-6-a — the CLI's dogfood surface: chat's two new legs, the readout.

Pinned here: the chat command passes ``--content-db`` / ``--rollout-stage``
through to ``open_host`` verbatim; not passing the stage flag reaches the
host as ``rollout_stage=None`` (the zero-open boundary — the CLI never
substitutes a stage of its own); an unknown stage word is a human sentence
and exit 2 before anything is opened; the wiring's ``error_detectors``
default stays ``None`` (backward compatibility, m7's pin); and the
``observations`` command reads one real app.db's durable facts — the six
indicator words, the gate/moment/action counts with the drift signal, and
the known false-positive faces — without writing anything.
"""

from __future__ import annotations

import inspect
import io
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

import elc.cli
from elc.cli import main
from elc.conversation.types import CommitUserTurn
from elc.host import Host, open_host
from elc.persona.provider import ScriptedPersonaProvider
from elc.persona.types import ProviderOutput
from elc.platform.types import (
    ClientMessageId,
    ConversationId,
    EvidenceModality,
    GoalId,
    GoalModality,
    GoalVersion,
    InputId,
    InteractionChannel,
    Ok,
    PolicyVersion,
    Result,
    TargetId,
)
from elc.runtime.automatic_turn import AutomaticTurnWiring
from elc.runtime.types import InputEnvelope, TurnStatus
from elc.teaching.rollout import OBSERVATION_SPECS, RolloutStage
from elc.user_config.types import (
    LearningGoal,
    LearningGoalPortfolio,
    TeachingFrequency,
    TeachingPolicyProfile,
)

CONV = ConversationId("d6a-cli-conv")
ERROR_TEXT = "Any way, let's continue with the plan."
REPLY = "d6a cli reply"


def run(argv: list[str], **kwargs: object) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = main(argv, stdout=out, stderr=err, **kwargs)  # type: ignore[arg-type]
    return code, out.getvalue(), err.getvalue()


def provider() -> ScriptedPersonaProvider:
    return ScriptedPersonaProvider(script=(ProviderOutput(text=REPLY),))


class _StubHost:
    """Just enough host for ``_chat`` over an empty stdin."""

    epoch = "epoch-stub"

    def open_conversation(
        self, conversation_id: ConversationId
    ) -> Result[ConversationId]:
        return Ok(conversation_id)

    def startup_recovery(self) -> Result[object]:
        return Ok(object())

    def close(self) -> None:
        return None


def test_chat_passes_content_db_and_rollout_stage_to_open_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    received: dict[str, object] = {}

    def recording_open_host(app_db_path: object, **kwargs: object) -> _StubHost:
        received["app_db"] = app_db_path
        received.update(kwargs)
        return _StubHost()

    monkeypatch.setattr(elc.cli, "open_host", recording_open_host)
    content_db = tmp_path / "content.db"
    content_db.write_bytes(b"not a real artifact (open_host is stubbed)")
    code, _, err = run(
        [
            "chat",
            "--app-db",
            str(tmp_path / "app.db"),
            "--base-url",
            "https://offline.invalid/v1",
            "--model",
            "offline-model",
            "--api-key-env",
            "D6A_UNSET_KEY_VAR",
            "--content-db",
            str(content_db),
            "--rollout-stage",
            "Study-first",
        ],
        stdin=io.StringIO(""),
        provider=provider(),
    )
    assert (code, err) == (0, "")
    assert received["content_db_path"] == str(content_db)
    assert received["rollout_stage"] is RolloutStage.STUDY_FIRST


def test_chat_without_the_stage_flag_declares_no_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    received: dict[str, object] = {}

    def recording_open_host(app_db_path: object, **kwargs: object) -> _StubHost:
        received.update(kwargs)
        return _StubHost()

    monkeypatch.setattr(elc.cli, "open_host", recording_open_host)
    content_db = tmp_path / "content.db"
    content_db.write_bytes(b"stub")
    code, _, err = run(
        [
            "chat",
            "--app-db",
            str(tmp_path / "app.db"),
            "--base-url",
            "https://offline.invalid/v1",
            "--model",
            "offline-model",
            "--api-key-env",
            "D6A_UNSET_KEY_VAR",
            "--content-db",
            str(content_db),
        ],
        stdin=io.StringIO(""),
        provider=provider(),
    )
    assert (code, err) == (0, "")
    assert received["content_db_path"] == str(content_db)
    assert received["rollout_stage"] is None


def test_an_unknown_stage_word_is_a_sentence_and_exit_2(
    tmp_path: Path,
) -> None:
    app_db = tmp_path / "app.db"
    code, _, err = run(
        [
            "chat",
            "--app-db",
            str(app_db),
            "--base-url",
            "https://offline.invalid/v1",
            "--model",
            "offline-model",
            "--api-key-env",
            "D6A_UNSET_KEY_VAR",
            "--rollout-stage",
            "study_first",
        ],
        stdin=io.StringIO(""),
        provider=provider(),
    )
    assert code == 2
    for word in ("manual/user-initiated", "Study-first", "Balanced", "Lounge"):
        assert word in err
    assert not app_db.exists()


def test_the_wiring_default_keeps_error_detectors_none() -> None:
    """Backward compatibility, pinned: a wiring built without the field has
    no producer, so every existing assembly behaves exactly as before."""

    parameter = inspect.signature(AutomaticTurnWiring).parameters[
        "error_detectors"
    ]
    assert parameter.default is None


@pytest.fixture(scope="module")
def pilot_content_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    from elc.content.build import build_content_db
    from elc.detection import DetectorRegistry
    from elc.detection.pilot import PILOT_VERSION, register_pilot

    path = tmp_path_factory.mktemp("d6a-cli-pilot") / "content.db"
    registry = DetectorRegistry()
    register_pilot(registry)
    build_content_db(
        path,
        detector_registry=registry,
        verification_pilot_version=PILOT_VERSION,
    )
    return path


def test_observations_prints_indicators_counts_and_fp_faces(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """One real app.db with one opened moment, then the readout over it."""

    app_db = tmp_path / "app.db"
    host = open_host(
        app_db,
        provider=provider(),
        content_db_path=pilot_content_db,
        rollout_stage=RolloutStage.STUDY_FIRST,
    )
    try:
        seed_and_open_one_moment(host)
    finally:
        host.close()
    code, out, err = run(["observations", "--app-db", str(app_db)])
    assert (code, err) == (0, "")
    for spec in OBSERVATION_SPECS:
        assert spec.indicator in out
    assert "gate_decision by decision" in out
    assert "ALLOW" in out
    assert "AWAITING_USER" in out
    assert "TERMINAL" in out
    assert "TARGET_NOT_EXECUTABLY_VERIFIED" in out
    assert "Thought" in out
    assert "I think" in out
    assert "Any way" in out
    # value-level pins (D-6-a review LOW-1): this database carries exactly
    # one ALLOW over an empty reason list, one AWAITING_USER moment, one
    # TERMINAL action, and a zero drift signal — the readout must answer
    # those numbers, not merely name the rows (the review's m6 mutation
    # hardcoded every count to zero and stayed green against the pins above)
    assert "ALLOW | [] | 1" in out
    assert "AWAITING_USER | 1" in out
    assert "TERMINAL | 1" in out
    assert (
        "gate rows naming TARGET_NOT_EXECUTABLY_VERIFIED"
        " (the drift signal): 0" in out
    )


def seed_and_open_one_moment(host: Host) -> None:
    """The online E2E's setup, compressed: policy + portfolio + the
    NOT_SCHEDULED row + one error turn (the moment must exist for the
    readout's counts to be non-trivial). All through the host's own
    controllers."""

    written = host.user_config.upsert_teaching_policy(
        TeachingPolicyProfile(
            teaching_policy_profile_id=host.user_id,
            policy_version=PolicyVersion("pv-d6a-cli"),
            teaching_frequency=TeachingFrequency.BALANCED,
        )
    )
    assert isinstance(written, Ok), written
    portfolio = host.user_config.upsert_goal_portfolio(
        LearningGoalPortfolio(
            goal_portfolio_id=host.user_id,
            goal_version=GoalVersion("gv-d6a-cli"),
            goals=(
                LearningGoal(
                    goal_id=GoalId("goal-d6a-cli"),
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
    row = host.curriculum.get_target(TargetId("res-discourse-anyway"))
    assert isinstance(row, Ok), row
    scheduled = host.scheduler.recompute_schedule_item(
        row.value.target_type,
        TargetId("res-discourse-anyway"),
        EvidenceModality(row.value.evidence_modality),
        datetime.now(tz=UTC).isoformat(),
    )
    assert isinstance(scheduled, Ok), scheduled
    assert isinstance(host.open_conversation(CONV), Ok)
    suffix = uuid.uuid4().hex
    command = CommitUserTurn(
        conversation_id=CONV,
        envelope=InputEnvelope(
            input_id=InputId(f"d6a-cli-{suffix}"),
            client_message_id=ClientMessageId(f"d6a-cli-msg-{suffix}"),
            conversation_id=str(CONV),
            persona_id=None,
            scene_id=None,
            interaction_channel=InteractionChannel.TEXT,
            raw_payload=ERROR_TEXT,
            received_at=datetime.now(tz=UTC).isoformat(),
        ),
        raw_content=ERROR_TEXT,
        runtime_version="runtime-d6a-cli",
    )
    result = host.coordinator.begin_turn(command)
    assert isinstance(result, Ok), result
    assert result.value.turn_status is TurnStatus.COMPLETED
