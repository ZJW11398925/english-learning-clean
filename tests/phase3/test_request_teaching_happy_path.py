"""VAL ⑥ — the request_teaching happy path and its command-turn boundaries.

The whole P3-1A slice, end to end:

    request_teaching(conversation_id, focus_target_id)
    → InputEnvelope(raw_payload = canonical TEACHING_REQUEST JSON)
    → UserTurn(raw_content="", normalized_content=NULL)
    → DecisionCycle (snapshot-stamped)
    → Gate USER_INITIATED OPEN → ALLOW
    → CP2 → TeachingMoment(OPENING) + active_teaching_lock
      + GenerationActionIntent(TEACHING_OPEN, PREPARED)
    → the opening delivery through the P1 pipeline (P3-1B)
    → TeachingMoment(AWAITING_USER) + turn_outcome = REPLIED_FULL

Boundaries pinned here:

- the command turn produces no TEXT_PRODUCTION/TEXT_COMPREHENSION evidence,
  no analysis artifact and no watermark move;
- the command turn never reaches the persona as an utterance: it is absent
  from the ConversationWindow while remaining in the canonical transcript;
- the lock is exclusive: a second request while a moment is open is denied
  with TEACHING_LOCK_CONFLICT (and no second moment exists);
- re-entry replays the durable outcome instead of running the Gate again;
- an unknown target is a deterministic DENY (TARGET_INVALID +
  CONTENT_INVALID — a target that does not exist has no valid content).
"""

from __future__ import annotations

import json
import sqlite3

from elc.conversation import SqliteConversationStore
from elc.persona import ScriptedPersonaProvider
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.types import ClientMessageId, Ok
from elc.runtime.controller import ConversationCoordinator
from elc.runtime.types import GenerationActionStatus, TurnStatus
from elc.teaching.request import (
    TeachingRequest,
    parse_teaching_request_payload,
    teaching_request_payload,
)
from elc.teaching.types import MomentSource, MomentState, PresentationPhase

from .conftest import CONV, begin_turn_ok, make_lease, make_teaching_coordinator

REQUESTED_AT = "2026-09-21T08:00:00+00:00"

FACT_TABLES = (
    "gate_execution_status",
    "gate_decision",
    "teaching_moment",
    "active_teaching_lock",
    "generation_action_intent",
)


def _request(
    client_message_id: str | None = None,
    target_id: str = "res-hedge-i-think",
    target_type: str = "RESOURCE",
) -> TeachingRequest:
    return TeachingRequest(
        conversation_id=CONV,
        focus_target_id=target_id,
        target_type=target_type,
        client_message_id=(
            ClientMessageId(client_message_id) if client_message_id else None
        ),
        requested_at=REQUESTED_AT,
    )


def _coordinator(
    store: SqliteConversationStore,
    generation_store,
    fence: RuntimeEpochFence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
    *,
    provider: ScriptedPersonaProvider | None = None,
) -> ConversationCoordinator:
    return make_teaching_coordinator(
        store,
        generation_store,
        make_lease(fence),
        provider if provider is not None else ScriptedPersonaProvider(),
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
    )


def _counts(db: sqlite3.Connection) -> dict[str, int]:
    return {
        table: int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        for table in FACT_TABLES
    }


def test_request_teaching_happy_path_opens_the_moment(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    generation_store,
    conversation,
    fence: RuntimeEpochFence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
) -> None:
    del conversation
    coordinator = _coordinator(
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
    )
    result = coordinator.request_teaching(_request("cm-teach-1"))
    assert isinstance(result, Ok), result
    opened = result.value
    assert opened.gate_execution_status == "SUCCEEDED"
    assert opened.gate_decision == "ALLOW"
    assert opened.moment_id is not None
    assert opened.action_id is not None
    # P3-1B completes the P3-1A stop point: the planned TEACHING_OPEN action
    # is dispatched through the P1 pipeline, so the command turn reaches its
    # real user-visible outcome (STATE_MACHINES §10: the outcome belongs to
    # the delivery) and the moment reaches AWAITING_USER — SM §1's "opening
    # delivery confirmed/estimated → AWAITING_USER".
    assert opened.moment_state is MomentState.AWAITING_USER
    assert opened.action_status is GenerationActionStatus.TERMINAL
    assert opened.turn_status is TurnStatus.COMPLETED
    assert opened.outcome == "REPLIED_FULL"
    assert opened.decision_cycle_id is not None

    assert _counts(db) == {
        "gate_execution_status": 1,
        "gate_decision": 1,
        "teaching_moment": 1,
        "active_teaching_lock": 1,
        "generation_action_intent": 1,
    }
    moment = teaching_controller.get_moment(opened.moment_id)
    assert isinstance(moment, Ok) and moment.value is not None
    assert moment.value.source is MomentSource.USER_INITIATED
    assert moment.value.presentation_phase is PresentationPhase.INITIAL_PROMPT
    assert moment.value.focus_target.target_id == "res-hedge-i-think"
    assert moment.value.target_mode == "RESOURCE_PRACTICE"
    assert moment.value.learning_intent == "ESTABLISH"
    assert moment.value.evidence_modality.value == "TEXT_PRODUCTION"
    # The opening prompt shows context only, so the ladder's support level is
    # CONTEXT_ONLY once it was really delivered (the CP2 row is written with
    # NONE because nothing had been shown yet at that instant).
    assert moment.value.support_level.value == "CONTEXT_ONLY"
    assert moment.value.attempt_index == 0
    assert moment.value.opened_at is not None

    # Cycle bindings: the Learning snapshot + watermark are stamped; the
    # planner/gate and version columns have no source in Phase 3.
    cycle = decision_cycle_store.get_turn_cycle(opened.turn_id, 0)
    assert isinstance(cycle, Ok) and cycle.value is not None
    assert cycle.value.learning_snapshot_id == moment.value.learning_snapshot_id
    assert cycle.value.evidence_watermark == moment.value.evidence_watermark
    assert cycle.value.planner_decision_id is None
    assert cycle.value.gate_decision_id is None
    assert cycle.value.curriculum_version is None

    # The command turn: canonical payload + empty utterance.
    envelope = db.execute("SELECT raw_payload FROM input_envelope").fetchone()
    assert envelope is not None
    payload = parse_teaching_request_payload(str(envelope[0]))
    assert payload["type"] == "TEACHING_REQUEST"
    assert payload["focus_target_id"] == "res-hedge-i-think"
    user_turn = db.execute(
        "SELECT raw_content, normalized_content FROM user_turn"
    ).fetchone()
    assert user_turn == ("", None)


def test_command_turn_produces_no_evidence_and_no_window_entry(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    generation_store,
    conversation,
    fence: RuntimeEpochFence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
) -> None:
    coordinator = _coordinator(
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
    )
    result = coordinator.request_teaching(_request("cm-teach-2"))
    assert isinstance(result, Ok), result

    # No learning leg ran: no artifact, no group/claim, no watermark move.
    for table in ("analysis_artifact", "evidence_group", "evidence_claim"):
        assert db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
    assert learning.get_evidence_watermark() == 0

    # The transcript keeps the UserTurn (CP0 truth) …
    slice_ = store.get_canonical_turn_slice(result.value.turn_id)
    assert isinstance(slice_, Ok) and slice_.value is not None
    assert slice_.value.user_turn.raw_content == ""

    # … but the persona-visible window excludes the command turn.
    window = store.get_conversation_window(CONV, 20)
    assert isinstance(window, Ok)
    assert window.value.slices == ()

    # A normal turn afterwards still sees only real utterances.
    normal = _coordinator(
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
    )
    begin_turn_ok(normal, conversation, "cm-teach-after", "hello there")
    window_after = store.get_conversation_window(CONV, 20)
    assert isinstance(window_after, Ok)
    assert [
        slice_.user_turn.raw_content for slice_ in window_after.value.slices
    ] == ["hello there"]


def test_second_request_is_denied_by_the_active_lock(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    generation_store,
    conversation,
    fence: RuntimeEpochFence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
) -> None:
    del conversation
    coordinator = _coordinator(
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
    )
    first = coordinator.request_teaching(_request("cm-teach-3"))
    assert isinstance(first, Ok) and first.value.moment_id is not None

    second = coordinator.request_teaching(
        _request("cm-teach-4", target_id="res-frame-id-like-to")
    )
    assert isinstance(second, Ok), second
    assert second.value.gate_decision == "DENY"
    assert second.value.reason_codes == ("TEACHING_LOCK_CONFLICT",)
    assert second.value.moment_id is None
    assert second.value.action_id is None

    # One moment, one lock, one action — the denial wrote only its cycle's
    # two Gate facts.
    counts = _counts(db)
    assert counts["teaching_moment"] == 1
    assert counts["active_teaching_lock"] == 1
    assert counts["generation_action_intent"] == 1
    assert counts["gate_decision"] == 2
    assert counts["gate_execution_status"] == 2
    deny = db.execute(
        "SELECT decision, reason_codes FROM gate_decision"
        " WHERE decision = 'DENY'"
    ).fetchone()
    assert deny == ("DENY", '["TEACHING_LOCK_CONFLICT"]')
    # The denied request never became a moment: its cycle stays frozen
    # with the DENY facts only.
    assert db.execute("SELECT COUNT(*) FROM decision_cycle").fetchone()[0] == 2


def test_reentry_replays_the_durable_outcome(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    generation_store,
    conversation,
    fence: RuntimeEpochFence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
) -> None:
    del conversation
    coordinator = _coordinator(
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
    )
    first = coordinator.request_teaching(_request("cm-teach-5"))
    assert isinstance(first, Ok)
    replay = coordinator.request_teaching(_request("cm-teach-5"))
    assert isinstance(replay, Ok)
    assert replay.value.turn_id == first.value.turn_id
    assert replay.value.moment_id == first.value.moment_id
    assert replay.value.action_id == first.value.action_id
    assert replay.value.gate_decision == "ALLOW"
    # No second Gate run: one cycle, one status row, one decision row.
    assert db.execute("SELECT COUNT(*) FROM decision_cycle").fetchone()[0] == 1
    assert db.execute(
        "SELECT COUNT(*) FROM gate_execution_status"
    ).fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM gate_decision").fetchone()[0] == 1


def test_unknown_target_is_deterministically_denied(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    generation_store,
    conversation,
    fence: RuntimeEpochFence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
) -> None:
    del conversation
    coordinator = _coordinator(
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
    )
    result = coordinator.request_teaching(
        _request("cm-teach-6", target_id="res-not-a-target")
    )
    assert isinstance(result, Ok), result
    assert result.value.gate_decision == "DENY"
    assert result.value.reason_codes == ("TARGET_INVALID", "CONTENT_INVALID")
    assert result.value.moment_id is None
    counts = _counts(db)
    assert counts["teaching_moment"] == 0
    assert counts["active_teaching_lock"] == 0
    assert counts["generation_action_intent"] == 0


def test_command_payload_and_window_marker_agree() -> None:
    """The ConversationWindow filter marker and the canonical payload
    builder cannot drift (conversation/store.py + elc.teaching.request)."""

    from elc.conversation.store import TEACHING_REQUEST_PAYLOAD_MARKER

    payload = teaching_request_payload(_request())
    assert TEACHING_REQUEST_PAYLOAD_MARKER in payload
    assert json.loads(payload)["type"] == "TEACHING_REQUEST"


def test_second_call_without_client_message_id_forms_a_new_command_turn(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    generation_store,
    conversation,
    fence: RuntimeEpochFence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
) -> None:
    """Review F1: ``client_message_id`` is OPTIONAL dedupe — with no dedupe
    key, a second call forms a NEW canonical command turn (never a silent
    CP0 replay of the first), and the still-active moment denies it at the
    Gate with TEACHING_LOCK_CONFLICT."""

    del conversation
    coordinator = _coordinator(
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
    )
    first = coordinator.request_teaching(_request())
    assert isinstance(first, Ok) and first.value.moment_id is not None

    second = coordinator.request_teaching(_request())
    assert isinstance(second, Ok), second
    assert second.value.turn_id != first.value.turn_id  # a new turn, not a replay
    assert second.value.gate_execution_status == "SUCCEEDED"
    assert second.value.gate_decision == "DENY"
    assert second.value.reason_codes == ("TEACHING_LOCK_CONFLICT",)
    assert second.value.moment_id is None

    # Two command turns (fresh input ids → two envelopes, two user turns),
    # still one moment and one lock.
    assert db.execute("SELECT COUNT(*) FROM input_envelope").fetchone()[0] == 2
    assert db.execute("SELECT COUNT(*) FROM user_turn").fetchone()[0] == 2
    assert db.execute("SELECT COUNT(*) FROM teaching_moment").fetchone()[0] == 1
    assert db.execute(
        "SELECT COUNT(*) FROM active_teaching_lock"
    ).fetchone()[0] == 1
    # The fresh ids are unique per call (no derived constant).
    ids = [
        str(row[0])
        for row in db.execute(
            "SELECT input_id FROM input_envelope ORDER BY input_id"
        )
    ]
    assert len(set(ids)) == 2


def test_client_message_id_dedupe_replays_instead_of_rerunning(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    generation_store,
    conversation,
    fence: RuntimeEpochFence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
) -> None:
    """Review F1, replay half: a repeat call WITH the same
    client_message_id dedupes at CP0 to the original command turn — one
    turn, one cycle, one Gate run."""

    del conversation
    coordinator = _coordinator(
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
    )
    first = coordinator.request_teaching(_request("cm-f1-dedupe"))
    assert isinstance(first, Ok)
    replay = coordinator.request_teaching(_request("cm-f1-dedupe"))
    assert isinstance(replay, Ok)
    assert replay.value.turn_id == first.value.turn_id
    assert replay.value.moment_id == first.value.moment_id
    assert replay.value.action_id == first.value.action_id
    assert db.execute("SELECT COUNT(*) FROM input_envelope").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM user_turn").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM decision_cycle").fetchone()[0] == 1
    assert db.execute(
        "SELECT COUNT(*) FROM gate_execution_status"
    ).fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM gate_decision").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM teaching_moment").fetchone()[0] == 1
