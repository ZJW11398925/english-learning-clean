"""The full-chain composition root (D-5) — the second assembly tier, for real.

Two content.dbs built in this module decide every gate reading below: the
**default build** (``detector_registry=None``, zero ``EXECUTABLY_VERIFIED``
rows) and the **pilot build** (the D-3 registry, twelve EV rows). The gate
answers are artifact facts of those two files — the numbers are pinned here
and move only when the corpus or the pilot set does. The prep-1 tier is
pinned field for field: without a ``content_db_path`` every full-chain leg is
``None``, and the gate read face refuses instead of manufacturing a verdict.
"""

from __future__ import annotations

import io
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from elc.cli import main
from elc.content.build import build_content_db
from elc.conversation.types import CommitUserTurn
from elc.detection import DetectorRegistry
from elc.detection.pilot import register_pilot
from elc.host import LOCAL_V1_USER_ID, Host, open_host
from elc.learning.store import LOCAL_V1_DEFAULT_USER_SCOPE
from elc.persona.provider import ScriptedPersonaProvider
from elc.persona.types import ProviderOutput
from elc.platform.types import (
    ClientMessageId,
    ConversationId,
    DomainErrorCode,
    Err,
    InputId,
    InteractionChannel,
    Ok,
    UserId,
)
from elc.runtime.recovery import RECOVERY_KIND_TURN
from elc.runtime.types import InputEnvelope, TurnStatus
from elc.teaching.rollout import (
    RolloutStage,
    RolloutVerdict,
    stage_allows_automatic,
)
from tests.conftest import MIGRATION_IDS

CONV = ConversationId("d5-conv")
REPLY = "d5 reply"

#: The full-chain leg names of :class:`elc.host.Host` — the two tiers differ
#: exactly on these (``None`` in the prep-1 tier, built in the full chain).
FULL_CHAIN_LEGS = (
    "rollout_stage",
    "user_id",
    "user_config",
    "learning_store",
    "learning_controller",
    "teaching",
    "content_store",
    "curriculum",
    "targets",
    "supply",
    "silent",
    "scheduler",
    "planner_store",
    "ledger",
    "projections",
    "persona_views",
    "automatic",
)

#: The faces the automatic wiring carries once assembled — the surface the
#: missing-leg mutation (one ``=None`` in the assembly) must turn red on.
WIRING_FACES = (
    "planner_store",
    "teaching",
    "learning",
    "scheduler",
    "user_config",
    "curriculum",
    "supply",
    "ledger",
    "session_budget",
)


@pytest.fixture(scope="module")
def default_content_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One built content.db, library defaults: zero EXECUTABLY_VERIFIED."""

    path = tmp_path_factory.mktemp("d5-default") / "content.db"
    build_content_db(path)
    return path


@pytest.fixture(scope="module")
def pilot_content_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One built content.db over the D-3 pilot registry: twelve EV rows."""

    path = tmp_path_factory.mktemp("d5-pilot") / "content.db"
    registry = DetectorRegistry()
    register_pilot(registry)
    build_content_db(path, detector_registry=registry)
    return path


def command(text: str) -> CommitUserTurn:
    suffix = uuid.uuid4().hex
    return CommitUserTurn(
        conversation_id=CONV,
        envelope=InputEnvelope(
            input_id=InputId(f"d5-{suffix}"),
            client_message_id=ClientMessageId(f"d5-msg-{suffix}"),
            conversation_id=str(CONV),
            persona_id=None,
            scene_id=None,
            interaction_channel=InteractionChannel.TEXT,
            raw_payload=text,
            received_at=datetime.now(tz=UTC).isoformat(),
        ),
        raw_content=text,
        runtime_version="runtime-v1",
    )


def scripted(text: str = REPLY) -> ScriptedPersonaProvider:
    return ScriptedPersonaProvider(script=(ProviderOutput(text=text),))


def full(app_db: Path, content_db: Path, **kwargs: object) -> Host:
    """One full-chain host over the given artifact (provider scripted)."""

    return open_host(
        app_db,
        provider=scripted(),  # type: ignore[arg-type]
        content_db_path=content_db,
        **kwargs,
    )


def count(db: object, table: str) -> int:
    return int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# group 1 — the prep-1 tier is untouched, field for field
# ---------------------------------------------------------------------------


def test_the_default_tier_stays_field_for_field_prep1(tmp_path: Path) -> None:
    host = open_host(tmp_path / "app.db", provider=scripted())
    try:
        assert set(host.applied_migrations) == set(MIGRATION_IDS)
        for name in FULL_CHAIN_LEGS:
            assert getattr(host, name) is None, name
        # and the gate read face answers the honest refusal — never a verdict
        # manufactured out of a missing leg
        gate = host.content_rollout_gate()
        assert isinstance(gate, Err)
        assert gate.error.code is DomainErrorCode.DEPENDENCY_UNAVAILABLE
    finally:
        host.close()


# ---------------------------------------------------------------------------
# group 2 — the full chain builds every optional leg and the faces answer
# ---------------------------------------------------------------------------


def test_the_full_chain_assembles_every_optional_leg(
    tmp_path: Path, default_content_db: Path
) -> None:
    host = full(tmp_path / "app.db", default_content_db)
    try:
        assert set(host.applied_migrations) == set(MIGRATION_IDS)
        for name in FULL_CHAIN_LEGS:
            if name == "rollout_stage":
                # not a leg but the passthrough value: the zero-open default
                assert getattr(host, name) is None
            else:
                assert getattr(host, name) is not None, name
        wiring = host.automatic
        assert wiring is not None
        for name in WIRING_FACES:
            assert getattr(wiring, name) is not None, name
        assert wiring.user_id == host.user_id
        # behavioral spot checks: the curriculum face reads the real artifact
        # and the target provider resolves a target the artifact declares
        readiness = host.curriculum.readiness_by_target()  # type: ignore[union-attr]
        assert isinstance(readiness, Ok)
        assert readiness.value
        ready = [
            assessment.target_id
            for assessment in readiness.value
            if assessment.level is not None
        ]
        resolved = host.targets.resolve("RESOURCE", ready[0])  # type: ignore[union-attr]
        assert isinstance(resolved, Ok), resolved
    finally:
        host.close()


# ---------------------------------------------------------------------------
# group 3 — the zero-open boundary: wired, but fail-closed without a stage
# ---------------------------------------------------------------------------


def test_without_a_declared_stage_the_full_chain_stays_fail_closed(
    tmp_path: Path, default_content_db: Path
) -> None:
    host = full(tmp_path / "app.db", default_content_db)
    try:
        assert isinstance(host.open_conversation(CONV), Ok)
        result = host.coordinator.begin_turn(command("hello full chain"))
        assert isinstance(result, Ok), result
        assert result.value.turn_status is TurnStatus.COMPLETED
        assert result.value.reply_text == REPLY
        # the wiring exists and carries no stage — the host never declares one
        assert host.rollout_stage is None
        assert host.automatic is not None
        assert host.automatic.rollout_stage is None
        assert stage_allows_automatic(None) is False
        # and the behavior: a full turn through the wired coordinator opened
        # no teaching moment and ran no gate
        assert count(host.db, "teaching_moment") == 0
        assert count(host.db, "gate_decision") == 0
    finally:
        host.close()


def test_a_declared_stage_passes_through_verbatim(
    tmp_path: Path, default_content_db: Path
) -> None:
    host = full(
        tmp_path / "app.db",
        default_content_db,
        rollout_stage=RolloutStage.STUDY_FIRST,
    )
    try:
        assert host.rollout_stage is RolloutStage.STUDY_FIRST
        assert host.automatic is not None
        assert host.automatic.rollout_stage is RolloutStage.STUDY_FIRST
    finally:
        host.close()


# ---------------------------------------------------------------------------
# group 4 — the gate read face answers from artifact facts, both states
# ---------------------------------------------------------------------------


def test_the_gate_read_face_answers_from_artifact_facts(
    tmp_path: Path,
    default_content_db: Path,
    pilot_content_db: Path,
) -> None:
    plain_host = full(tmp_path / "plain.db", default_content_db)
    pilot_host = full(tmp_path / "pilot.db", pilot_content_db)
    try:
        plain = plain_host.content_rollout_gate()
        assert isinstance(plain, Ok)
        pilot = pilot_host.content_rollout_gate()
        assert isinstance(pilot, Ok)
        # default build: the R4 row clears the floor with 52 targets and the
        # provenance leg holds every one of them back
        row = plain.value.row("automatic CURRENT_USER_ERROR")
        assert (row.usable_targets, row.blocked_by_provenance) == (0, 52)
        assert row.verdict is RolloutVerdict.HOLD
        assert plain.value.verdict is RolloutVerdict.HOLD
        # pilot build: twelve EV targets serve the row; forty are held back
        row = pilot.value.row("automatic CURRENT_USER_ERROR")
        assert (row.usable_targets, row.blocked_by_provenance) == (12, 40)
        assert row.verdict is RolloutVerdict.GO
        assert pilot.value.verdict is RolloutVerdict.GO
        # the three unmarked rows never read provenance: identical counts in
        # both reports (any drift there is a wiring bug, not a reading)
        for word in (
            "PROBE",
            "user-initiated teaching",
            "automatic general/review",
        ):
            assert pilot.value.row(word).usable_targets == (
                plain.value.row(word).usable_targets
            )
    finally:
        plain_host.close()
        pilot_host.close()


# ---------------------------------------------------------------------------
# group 5 — the CLI gate command, end to end over both artifacts
# ---------------------------------------------------------------------------


def test_the_cli_gate_subcommand_codes_the_verdict(
    default_content_db: Path, pilot_content_db: Path
) -> None:
    out, err = io.StringIO(), io.StringIO()
    code = main(
        ["gate", "--content-db", str(pilot_content_db)],
        stdout=out,
        stderr=err,
    )
    lines = out.getvalue().splitlines()
    assert code == 0
    row_lines = [
        line for line in lines if line.startswith("automatic CURRENT_USER_ERROR")
    ]
    assert len(row_lines) == 1
    assert "usable targets 12" in row_lines[0]
    assert "40 blocked by provenance" in row_lines[0]
    assert any(line == "verdict: GO (automatic rows: GO)" for line in lines)
    assert any("opens nothing" in line for line in lines)  # the scope note
    assert err.getvalue() == ""

    out, err = io.StringIO(), io.StringIO()
    code = main(
        ["gate", "--content-db", str(default_content_db)],
        stdout=out,
        stderr=err,
    )
    lines = out.getvalue().splitlines()
    assert code == 1
    assert any("usable targets 0 → HOLD" in line for line in lines)
    assert any(line == "verdict: HOLD (automatic rows: HOLD)" for line in lines)


# ---------------------------------------------------------------------------
# group 6 — close releases everything, and everything is re-openable
# ---------------------------------------------------------------------------


def test_close_releases_every_connection_including_the_artifact(
    tmp_path: Path, default_content_db: Path
) -> None:
    host = full(tmp_path / "app.db", default_content_db)
    content_store = host.content_store
    assert content_store is not None
    first_epoch = host.epoch
    host.close()
    # the artifact's connection is closed: the store's own read face answers
    # the way sqlite answers a closed connection
    with pytest.raises(sqlite3.ProgrammingError):
        content_store.entity_ids()
    host.close()  # idempotent: closing twice changes nothing
    reopened = full(tmp_path / "app.db", default_content_db)
    try:
        assert reopened.epoch == first_epoch + 1
    finally:
        reopened.close()


# ---------------------------------------------------------------------------
# group 7 — startup recovery through the full chain, compared honestly
# ---------------------------------------------------------------------------


def test_full_chain_startup_recovery_runs_and_reports_honestly(
    tmp_path: Path, default_content_db: Path
) -> None:
    first = full(tmp_path / "app.db", default_content_db)
    try:
        assert isinstance(first.open_conversation(CONV), Ok)
        cp0 = first.conversations.commit_user_turn(command("left behind"))
        assert isinstance(cp0, Ok), cp0
    finally:
        first.close()

    second = full(tmp_path / "app.db", default_content_db)
    try:
        assert second.epoch == first.epoch + 1
        recovery = second.startup_recovery()
        assert isinstance(recovery, Ok), recovery
        assert [(item.kind, item.id) for item in recovery.value.plan] == [
            (RECOVERY_KIND_TURN, str(cp0.value.turn_id))
        ]
        assert recovery.value.closed_turns == ()
    finally:
        second.close()

    # the honest comparison: the same residue through the prep-1 tier produces
    # the same plan shape — the teaching leg's presence manufactures no
    # closure the durable facts do not carry (the host claims recovery runs
    # and reports, not that it finishes teaching residue)
    bare = open_host(tmp_path / "bare.db", provider=scripted())
    try:
        assert isinstance(bare.open_conversation(CONV), Ok)
        bare_cp0 = bare.conversations.commit_user_turn(command("left behind"))
        assert isinstance(bare_cp0, Ok), bare_cp0
    finally:
        bare.close()
    bare_second = open_host(tmp_path / "bare.db", provider=scripted())
    try:
        bare_recovery = bare_second.startup_recovery()
        assert isinstance(bare_recovery, Ok), bare_recovery
        assert [
            (item.kind, item.id) for item in bare_recovery.value.plan
        ] == [(RECOVERY_KIND_TURN, str(bare_cp0.value.turn_id))]
        assert bare_recovery.value.closed_turns == ()
    finally:
        bare_second.close()


# ---------------------------------------------------------------------------
# group 8 — the user identity is the repository's V1 constant, verbatim
# ---------------------------------------------------------------------------


def test_the_assembly_binds_the_local_v1_user_identity(
    tmp_path: Path, default_content_db: Path
) -> None:
    host = full(tmp_path / "app.db", default_content_db)
    try:
        assert host.user_id == UserId(LOCAL_V1_DEFAULT_USER_SCOPE)
        assert LOCAL_V1_USER_ID == UserId(LOCAL_V1_DEFAULT_USER_SCOPE)
        assert host.automatic is not None
        assert host.automatic.user_id == host.user_id
        assert host.persona_views is not None
        assert host.persona_views.user_id == host.user_id
    finally:
        host.close()
