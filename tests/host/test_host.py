"""The composition root (prep-1 deliverable C) — a real app.db, fully offline.

Three cases: a real turn through the production stores; a reopen that opens a
new epoch and finds the previous epoch's residue (the RA §22 scan naming it);
and the provider-failure path, where the failure is a value and the transcript
stays empty (DOMAIN_MODEL §3: undelivered output never enters it).

No teaching port is wired here, and that is the honest assembly rather than an
omission: without ``TeachingController`` the startup plan carries TURN items
only and *closes* nothing (``ConversationCoordinator.run_startup_recovery``'s
docstring states it), so the residue stays visible in the plan — this cut
claims recovery runs and reports, not that it finishes teaching residue.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from elc.conversation.types import CommitUserTurn
from elc.host import Host, open_host
from elc.persona.provider import ScriptedPersonaProvider
from elc.persona.types import ProviderOutput
from elc.platform.db.decision_cycle_store import SqliteDecisionCycleStore
from elc.platform.db.generation_store import SqliteGenerationStore
from elc.platform.types import (
    ClientMessageId,
    ConversationId,
    InputId,
    InteractionChannel,
    Ok,
)
from elc.runtime.recovery import RECOVERY_KIND_TURN
from elc.runtime.types import InputEnvelope, TurnStatus
from tests.conftest import MIGRATION_IDS

CONV = ConversationId("host-conv")
REPLY = "host reply"


def command(text: str) -> CommitUserTurn:
    suffix = uuid.uuid4().hex
    return CommitUserTurn(
        conversation_id=CONV,
        envelope=InputEnvelope(
            input_id=InputId(f"host-{suffix}"),
            client_message_id=ClientMessageId(f"host-msg-{suffix}"),
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


def count(db: object, table: str) -> int:
    return int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])  # type: ignore[attr-defined]


def test_the_host_assembles_the_production_stores_and_runs_a_turn(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "app.db"
    provider = scripted()
    host = open_host(db_path, provider=provider)
    try:
        assert set(host.applied_migrations) == set(MIGRATION_IDS)
        assert host.epoch == 1
        # The production assembly: two *separate* real stores, and the exact
        # shipped classes — never tests/conftest's AssemblyGenerationStore,
        # which only the suite may subclass.
        assert type(host.generation) is SqliteGenerationStore
        assert type(host.decision_cycles) is SqliteDecisionCycleStore
        assert host.decision_cycles is not host.generation
        assert isinstance(host.open_conversation(CONV), Ok)

        result = host.coordinator.begin_turn(command("hello host"))
        assert isinstance(result, Ok), result
        completion = result.value
        assert completion.turn_status is TurnStatus.COMPLETED
        assert completion.outcome == "REPLIED_FULL"
        assert completion.reply_text == REPLY
        assert completion.delivery_state == "SENT_COMPLETE"
        assert provider.call_count == 1
        assert count(host.db, "assistant_turn") == 1
    finally:
        host.close()


def test_a_reopen_opens_a_new_epoch_and_the_old_epochs_turn_is_in_the_plan(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "app.db"
    first = open_host(db_path, provider=scripted())
    try:
        assert isinstance(first.open_conversation(CONV), Ok)
        # CP0 only: the turn is durable and nonterminal when this epoch dies.
        cp0 = first.conversations.commit_user_turn(command("left behind"))
        assert isinstance(cp0, Ok), cp0
    finally:
        first.close()

    second = open_host(db_path, provider=scripted())
    try:
        assert second.epoch == first.epoch + 1
        assert second.applied_migrations == ()  # migrations are idempotent
        recovery = second.startup_recovery()
        assert isinstance(recovery, Ok), recovery
        plan = recovery.value.plan
        assert [(item.kind, item.id) for item in plan] == [
            (RECOVERY_KIND_TURN, str(cp0.value.turn_id))
        ]
        # No teaching port: the plan names the residue, the closure face is the
        # teaching pipeline's and this host does not pretend to run it.
        assert recovery.value.closed_turns == ()
    finally:
        second.close()


def test_provider_failure_is_a_value_and_leaves_the_transcript_empty(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "app.db"
    provider = ScriptedPersonaProvider(
        script=(ProviderOutput(text=None, error="offline provider exploded"),)
    )
    host: Host = open_host(db_path, provider=provider)
    try:
        assert isinstance(host.open_conversation(CONV), Ok)
        result = host.coordinator.begin_turn(command("hello host"))
        assert isinstance(result, Ok), result
        completion = result.value
        assert completion.reply_text is None
        assert completion.failure_reason == "offline provider exploded"
        assert completion.outcome == "FAILED_USER_VISIBLE"
        assert completion.turn_status is TurnStatus.FAILED_FINAL
        assert count(host.db, "assistant_turn") == 0
    finally:
        host.close()
