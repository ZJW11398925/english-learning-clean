"""P4-2 ⑤ — the RELATIONSHIP projection end to end (TASK-OPI-4d516e4f.9).

The executor (``elc.relationship.projection``) is driven through the real
CP4 runtime, the real durable queue and the real stores, so this file is
about behaviour, not about wiring:

- a scripted candidate on a canonical chat turn becomes a durable ACTIVE
  relationship memory, visible through the domain view, and its job lands
  COMMITTED with the base this run recomputed;
- a command turn (a teaching request / reply) projects *nothing*: the
  Recorder's durable classifier is the single authority for that red line,
  and this executor deliberately does not re-derive it (the source pin
  below);
- a conversation without a persona, and a summary assembled for another
  Persona×User pair, are both refused before any write — the assembly
  consistency check DEC-…115 待裁 B 附条件 mandates.
"""

from __future__ import annotations

import sqlite3

from elc.platform.types import ClientMessageId, Ok
from elc.relationship import (
    RelationshipController,
    RelationshipProjectionExecutor,
    RelationshipRecorder,
    SamePersonaExistingRelationshipSummary,
)
from elc.runtime.controller import ConversationCoordinator, TeachingReplyRequest
from elc.runtime.projections import (
    PROJECTION_TYPE_RELATIONSHIP,
    CP4ProjectionRuntime,
    base_version_for,
    projection_id_for,
)
from elc.teaching.request import TeachingRequest
from tests.conftest import SRC_ROOT

from .conftest import (
    CANONICAL_ANSWER,
    CONV,
    FOCUS_TARGET,
    PERSONA_A,
    PERSONA_B,
    REL_USER,
    REQUESTED_AT,
    ScriptedCandidates,
    commit_chat_turn,
    memory_candidate,
    memory_rows,
    open_conversation_for,
    projection_job_row,
    projection_job_rows,
)
from .conftest import attempt as make_attempt


class _ForeignScopeController(RelationshipController):
    """A controller whose summary is assembled for another persona — exactly
    the mis-assembly the DEC-…115 待裁 B check exists for."""

    def get_existing_summary(self, persona_id, user_id):
        del persona_id
        return Ok(
            SamePersonaExistingRelationshipSummary(
                persona_id=PERSONA_B, user_id=user_id, memories=()
            )
        )


def _project(
    *,
    store,
    projection_store,
    controller,
    candidates,
    user_id=REL_USER,
) -> CP4ProjectionRuntime:
    """The runtime over one RELATIONSHIP executor built from the given
    pieces (the test states the controller it means to probe)."""

    executor = RelationshipProjectionExecutor(
        recorder=RelationshipRecorder(store),
        controller=controller,
        conversation=store,
        user_id=user_id,
        candidates=ScriptedCandidates(candidates),
    )
    return CP4ProjectionRuntime(
        store=projection_store, executors=(executor,), turns=store
    )


def _open_and_reply(
    coordinator: ConversationCoordinator, conversation, *, tag: str
):
    """One real teaching request + reply over one persona conversation (the
    command turns this file is about)."""

    opened = coordinator.request_teaching(
        TeachingRequest(
            conversation_id=conversation,
            focus_target_id=FOCUS_TARGET,
            client_message_id=ClientMessageId(f"cm-{tag}-open"),
            requested_at=REQUESTED_AT,
        )
    )
    assert isinstance(opened, Ok), opened
    assert opened.value.gate_decision == "ALLOW"
    replied = coordinator.respond_to_teaching(
        TeachingReplyRequest(
            conversation_id=conversation,
            envelope=make_attempt(CANONICAL_ANSWER),
            client_message_id=ClientMessageId(f"cm-{tag}-reply"),
            requested_at=REQUESTED_AT,
        )
    )
    assert isinstance(replied, Ok), replied
    return opened.value, replied.value


# -- ⑤ the happy path -------------------------------------------------------


def test_one_chat_turn_becomes_one_visible_relationship_memory(
    db: sqlite3.Connection,
    store,
    relationship_controller,
    relationship_store,
    projecting_coordinator,
    scripted_candidates: ScriptedCandidates,
) -> None:
    conversation = open_conversation_for(store, "conv-proj-memory", PERSONA_A)
    scripted_candidates.candidates = (
        memory_candidate("The user lives in Berlin."),
    )
    # The base the job will build on: the empty (pre-write) summary.
    empty = relationship_controller.get_existing_summary(PERSONA_A, REL_USER)
    assert isinstance(empty, Ok)
    expected_base = base_version_for(empty.value)

    turn = commit_chat_turn(
        projecting_coordinator,
        "cm-proj-memory",
        "I live in Berlin.",
        1,
        conversation=conversation,
    )
    assert turn.outcome == "REPLIED_FULL"

    job_id = projection_id_for(PROJECTION_TYPE_RELATIONSHIP, turn.turn_id)
    row = projection_job_row(db, job_id)
    assert row[5] == "COMMITTED"
    assert row[6] == 1
    assert row[4] == expected_base

    # The memory is durable, ACTIVE, and visible through the domain's own
    # view — the §5 write flow ran end to end.
    rows = memory_rows(db)
    assert len(rows) == 1
    assert rows[0][1] == str(PERSONA_A)
    assert rows[0][2] == str(REL_USER)
    assert rows[0][5] == "The user lives in Berlin."
    assert rows[0][7] == "ACTIVE"
    view = relationship_store.get_relationship_view(PERSONA_A, REL_USER)
    assert isinstance(view, Ok)
    assert [m.canonical_content for m in view.value.active_memories] == [
        "The user lives in Berlin."
    ]
    assert view.value.active_memories[0].source_turn_id == turn.turn_id

    # A second turn over the same conversation adds the second memory, and
    # its base is a different digest (the first memory is part of the base
    # now).
    scripted_candidates.candidates = (
        memory_candidate("The user reads every evening."),
    )
    second = commit_chat_turn(
        projecting_coordinator,
        "cm-proj-memory-2",
        "I read every evening.",
        2,
        conversation=conversation,
    )
    assert second.outcome == "REPLIED_FULL"
    second_row = projection_job_row(
        db, projection_id_for(PROJECTION_TYPE_RELATIONSHIP, second.turn_id)
    )
    assert second_row[5] == "COMMITTED"
    assert second_row[4] != expected_base
    assert len(memory_rows(db)) == 2


def test_the_executor_projects_nothing_without_candidates(
    db: sqlite3.Connection,
    store,
    projecting_coordinator,
) -> None:
    """The default fixture wiring: a provider with no scripted assertions
    (the honest v0 assembly). The job still runs and commits — it simply has
    nothing to remember."""

    conversation = open_conversation_for(store, "conv-proj-empty", PERSONA_A)
    turn = commit_chat_turn(
        projecting_coordinator,
        "cm-proj-empty",
        "I live in Berlin.",
        1,
        conversation=conversation,
    )
    assert turn.outcome == "REPLIED_FULL"
    assert memory_rows(db) == []
    row = projection_job_row(
        db, projection_id_for(PROJECTION_TYPE_RELATIONSHIP, turn.turn_id)
    )
    assert row[5] == "COMMITTED"


# -- ⑤ command turns project nothing ---------------------------------------


def test_a_command_turn_projects_no_memory(
    db: sqlite3.Connection,
    store,
    projecting_coordinator,
    scripted_candidates: ScriptedCandidates,
) -> None:
    """A teaching request and its reply are command turns: the Recorder's
    durable classifier refuses the assertions, so the projection commits
    with zero proposals and zero memories (VAL-…72 ⑤)."""

    conversation = open_conversation_for(store, "conv-proj-cmd", PERSONA_A)
    scripted_candidates.candidates = (
        memory_candidate("The user lives in Berlin."),
    )
    opened, replied = _open_and_reply(
        projecting_coordinator, conversation, tag="proj-cmd"
    )

    assert memory_rows(db) == []
    # Here only the reply turn carries a CP4 job: the live post-turn line
    # enqueues *canonical new* turns, and ``request_teaching`` stops at CP2
    # without being wired to it. The startup crash-gap scan is wider on
    # purpose — it covers every COMPLETED turn, command turns included — and
    # what keeps those projections memory-free is the Recorder's durable
    # command-turn classification, not a narrower scan.
    rows = projection_job_rows(db)
    assert len(rows) == 1
    assert rows[0][2] == str(replied.turn_id)
    assert rows[0][5] == "COMMITTED"
    assert str(opened.moment_id) != ""
    assert replied.evidence_commit_id is not None  # the reply itself was real


def test_the_run_detail_counts_the_recorder_refusals(
    db: sqlite3.Connection,
    store,
    projection_store,
    relationship_controller,
    coordinator: ConversationCoordinator,
) -> None:
    """The executor's return text is the honest count of what happened: the
    command turn's declared candidate reaches the Recorder and is refused
    there (RECORDER-side, not by a heuristic of ours), so the commit carries
    ``proposals=0 recorder_refusals=1``."""

    conversation = open_conversation_for(store, "conv-proj-count", PERSONA_A)
    _opened, replied = _open_and_reply(coordinator, conversation, tag="proj-count")
    runtime = _project(
        store=store,
        projection_store=projection_store,
        controller=relationship_controller,
        candidates=(memory_candidate("The user lives in Berlin."),),
    )
    runs = runtime.run_after_turn(conversation, replied.turn_id)
    assert isinstance(runs, Ok), runs
    assert [item.status.value for item in runs.value] == ["COMMITTED"]
    detail = runs.value[0].detail
    assert detail == (
        "committed: proposals=0 committed=0 controller_refusals=0"
        " recorder_refusals=1"
    )
    assert memory_rows(db) == []

    # The positive control on an ordinary turn of the same world: the same
    # declared candidate does become a proposal and is committed by the
    # controller.
    chat = commit_chat_turn(
        coordinator, "cm-proj-count-chat", "I live in Berlin.", 1,
        conversation=conversation,
    )
    accepted = runtime.run_after_turn(conversation, chat.turn_id)
    assert isinstance(accepted, Ok), accepted
    assert accepted.value[0].detail == (
        "committed: proposals=1 committed=1 controller_refusals=0"
        " recorder_refusals=0"
    )
    assert len(memory_rows(db)) == 1


def test_the_executor_never_re_derives_the_command_turn_classification() -> None:
    """The P4-G1 red line, seen from the projection side: the durable
    classifier inside the Recorder stays the *single* authority — the
    executor grows no second heuristic over the payload text."""

    executor_source = (
        SRC_ROOT / "relationship" / "projection.py"
    ).read_text(encoding="utf-8")
    assert "is_command_payload_turn" not in executor_source
    assert "TEACHING_REQUEST" not in executor_source
    recorder_source = (
        SRC_ROOT / "relationship" / "recorder.py"
    ).read_text(encoding="utf-8")
    assert "is_command_payload_turn" in recorder_source


# -- ⑤ refusals happen before any write ------------------------------------


def test_a_conversation_without_a_persona_is_refused_at_the_base(
    db: sqlite3.Connection,
    store,
    projection_store,
    relationship_controller,
    coordinator: ConversationCoordinator,
) -> None:
    runtime = _project(
        store=store,
        projection_store=projection_store,
        controller=relationship_controller,
        candidates=(memory_candidate("The user lives in Berlin."),),
    )
    turn = commit_chat_turn(coordinator, "cm-proj-nopersona", "I live in Berlin.", 1)
    runs = runtime.run_after_turn(CONV, turn.turn_id)
    assert isinstance(runs, Ok), runs
    assert [item.status.value for item in runs.value] == ["REJECTED"]
    assert "has no persona" in runs.value[0].detail
    job_id = projection_id_for(PROJECTION_TYPE_RELATIONSHIP, turn.turn_id)
    assert projection_job_row(db, job_id)[5] == "REJECTED"
    assert projection_job_row(db, job_id)[6] == 0  # never claimed
    assert memory_rows(db) == []


def test_a_mis_assembled_summary_is_refused_with_zero_writes(
    db: sqlite3.Connection,
    store,
    projection_store,
    relationship_store,
    coordinator: ConversationCoordinator,
) -> None:
    """DEC-…115 待裁 B 附条件: the summary the executor read must be scoped to
    the pair it writes for — otherwise it refuses with zero writes."""

    conversation = open_conversation_for(store, "conv-proj-scope", PERSONA_A)
    turn = commit_chat_turn(
        coordinator,
        "cm-proj-scope",
        "I live in Berlin.",
        1,
        conversation=conversation,
    )
    runtime = _project(
        store=store,
        projection_store=projection_store,
        controller=_ForeignScopeController(relationship_store),
        candidates=(memory_candidate("The user lives in Berlin."),),
    )
    runs = runtime.run_after_turn(conversation, turn.turn_id)
    assert isinstance(runs, Ok), runs
    assert [item.status.value for item in runs.value] == ["REJECTED"]
    assert "scope mismatch" in runs.value[0].detail
    assert str(PERSONA_B) in runs.value[0].detail
    job_id = projection_id_for(PROJECTION_TYPE_RELATIONSHIP, turn.turn_id)
    assert projection_job_row(db, job_id)[5] == "REJECTED"
    assert memory_rows(db) == []
    # Nothing leaked to either persona's view.
    for persona in (PERSONA_A, PERSONA_B):
        view = relationship_store.get_relationship_view(persona, REL_USER)
        assert isinstance(view, Ok)
        assert view.value.active_memories == ()
