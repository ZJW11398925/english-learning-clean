"""The ``seed`` command — the cold-start bootstrap, pinned end to end.

A brand-new app.db opens fine and helps nobody: no §5.1 teaching policy, no
goal portfolio, no §5.2 schedule rows — the planner's generators refuse every
candidate and automatic teaching can never trigger. ``elc seed`` writes the
three missing pieces through the host's own controllers, and this suite pins
the user's real path with zero manual preparation besides the command itself:

1. the cold-start loop — seed a fresh app.db, then a second host (the user's
   own ``chat`` process) opens the automatic moment from a plain user turn
   and the Gate ALLOWs it;
2. idempotence — running the command twice answers 0 with the same counts
   and the schedule table does not grow;
3. the default values — BALANCED policy, SPEAKING goal, read off the tables;
4. the EV set — the scheduled targets are exactly the artifact's
   ``EXECUTABLY_VERIFIED`` set, id for id;
5. the usage contract — a missing argument is a human sentence and exit 2,
   an unopenable content.db is exit 1.
"""

from __future__ import annotations

import io
import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from elc.cli import main
from elc.content.store import ContentStore
from elc.conversation.types import CommitUserTurn
from elc.host import open_host
from elc.persona.provider import ScriptedPersonaProvider
from elc.persona.types import ProviderOutput
from elc.platform.types import (
    ClientMessageId,
    ConversationId,
    InputId,
    InteractionChannel,
    Ok,
)
from elc.runtime.types import InputEnvelope, TurnStatus
from elc.teaching.rollout import RolloutStage

CONV = ConversationId("seed-conv")
ERROR_TEXT = "Any way, let's continue with the plan."
REPLY = "seed reply"
EV_TARGET = "res-discourse-anyway"


def run(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = main(argv, stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue()


@pytest.fixture(scope="module")
def pilot_content_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    from elc.content.build import build_content_db
    from elc.detection import DetectorRegistry
    from elc.detection.pilot import PILOT_VERSION, register_pilot

    path = tmp_path_factory.mktemp("seed-pilot") / "content.db"
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
            input_id=InputId(f"seed-{suffix}"),
            client_message_id=ClientMessageId(f"seed-msg-{suffix}"),
            conversation_id=str(CONV),
            persona_id=None,
            scene_id=None,
            interaction_channel=InteractionChannel.TEXT,
            raw_payload=text,
            received_at=datetime.now(tz=UTC).isoformat(),
        ),
        raw_content=text,
        runtime_version="runtime-seed",
    )


def schedule_row_count(app_db: Path) -> int:
    db = sqlite3.connect(app_db)
    try:
        return int(
            db.execute("SELECT COUNT(*) FROM schedule_item").fetchone()[0]
        )
    finally:
        db.close()


def test_seed_closes_the_cold_start_loop(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """Seed, then a second host — the user's own chat process, no manual
    preparation of any kind — opens the automatic moment from a plain user
    turn and the Gate ALLOWs it."""

    app_db = tmp_path / "app.db"
    code, out, err = run(
        [
            "seed",
            "--app-db",
            str(app_db),
            "--content-db",
            str(pilot_content_db),
        ]
    )
    assert (code, err) == (0, "")
    assert "schedule rows for" in out and "(skipped: none)" in out

    host = open_host(
        app_db,
        provider=ScriptedPersonaProvider(script=(ProviderOutput(text=REPLY),)),
        content_db_path=pilot_content_db,
        rollout_stage=RolloutStage.STUDY_FIRST,
    )
    try:
        assert isinstance(host.open_conversation(CONV), Ok)
        result = host.coordinator.begin_turn(command(ERROR_TEXT))
        assert isinstance(result, Ok), result
        assert result.value.turn_status is TurnStatus.COMPLETED
        moments = host.db.execute(
            "SELECT lifecycle_state, source, focus_target FROM teaching_moment"
        ).fetchall()
        assert len(moments) == 1
        assert moments[0][0] == "AWAITING_USER"
        assert moments[0][1] == "AUTOMATIC"
        assert EV_TARGET in str(moments[0][2])
        gate = host.db.execute(
            "SELECT decision FROM gate_decision"
        ).fetchall()
        assert gate == [("ALLOW",)]
    finally:
        host.close()


def test_rerunning_seed_is_idempotent(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    app_db = tmp_path / "app.db"
    argv = ["seed", "--app-db", str(app_db), "--content-db", str(pilot_content_db)]
    code1, out1, err1 = run(argv)
    assert (code1, err1) == (0, "")
    count_after_first = schedule_row_count(app_db)
    assert count_after_first > 0

    code2, out2, err2 = run(argv)
    assert (code2, err2) == (0, "")
    # the same counts, and the schedule table did not grow
    assert out1 == out2
    assert schedule_row_count(app_db) == count_after_first


def test_seed_writes_the_balanced_policy_and_speaking_goal(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    app_db = tmp_path / "app.db"
    code, _, err = run(
        ["seed", "--app-db", str(app_db), "--content-db", str(pilot_content_db)]
    )
    assert (code, err) == (0, "")
    db = sqlite3.connect(app_db)
    try:
        policies = db.execute(
            "SELECT teaching_policy_profile_id, policy_version,"
            " teaching_frequency FROM teaching_policy"
        ).fetchall()
        assert len(policies) == 1
        assert policies[0][1] == "pv-seed-v1"
        assert policies[0][2] == "BALANCED"
        portfolios = db.execute(
            "SELECT goal_version, goals, modality_weights FROM goal_portfolio"
        ).fetchall()
        assert len(portfolios) == 1
        goals = json.loads(portfolios[0][1])
        assert len(goals) == 1
        assert goals[0]["goal_id"] == "goal-seed-v1"
        assert goals[0]["goal_modality"] == "SPEAKING"
        # v3-d 清扫随迁：种子目标写的是真实目标句，不是占位散文。
        assert goals[0]["description"] == (
            "Hold a five-minute everyday conversation in English"
            " without switching back to Chinese."
        )
        assert "long-term" not in goals[0]["description"]
        assert json.loads(portfolios[0][2]) == {"SPEAKING": 1.0}
    finally:
        db.close()


def test_the_seeded_schedule_rows_are_exactly_the_ev_set(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    app_db = tmp_path / "app.db"
    code, out, _ = run(
        ["seed", "--app-db", str(app_db), "--content-db", str(pilot_content_db)]
    )
    assert code == 0
    store = ContentStore(pilot_content_db)
    try:
        provenance = store.provenance_levels()
        assert isinstance(provenance, Ok)
        ev_set = {
            entity_id
            for entity_id, level in provenance.value
            if level == "EXECUTABLY_VERIFIED"
        }
    finally:
        store.close()
    assert len(ev_set) == 12
    assert "12 schedule rows for 12 EV targets" in out
    db = sqlite3.connect(app_db)
    try:
        scheduled = {
            str(row[0])
            for row in db.execute(
                "SELECT target_id FROM schedule_item"
            ).fetchall()
        }
    finally:
        db.close()
    assert scheduled == ev_set
    for entity_id in ev_set:
        assert entity_id in scheduled


def test_seed_without_required_arguments_is_a_sentence_and_exit_2(
    tmp_path: Path,
) -> None:
    code, _, err = run(["seed", "--app-db", str(tmp_path / "app.db")])
    assert code == 2
    assert "--app-db" in err and "--content-db" in err
    code2, _, err2 = run(["seed"])
    assert code2 == 2
    assert "elc seed" in err2


def test_seed_with_an_unopenable_content_db_is_exit_1(
    tmp_path: Path,
) -> None:
    content_db = tmp_path / "content.db"
    content_db.write_bytes(b"not a database at all")
    code, _, err = run(
        [
            "seed",
            "--app-db",
            str(tmp_path / "app.db"),
            "--content-db",
            str(content_db),
        ]
    )
    assert code == 1
    assert "elc seed" in err
