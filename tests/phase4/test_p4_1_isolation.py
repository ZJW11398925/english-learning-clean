"""P4-1 ③ — Persona×User isolation (VAL-…5ba74efc.72 ③; IP §4 Acceptance③).

docs/DOMAIN_MODEL.md §5's unit is Persona × User, and §17 is blunt:
"Relationship 不跨 Persona 泄漏". BF-05 §29 adds that even a shareable fact
travels through UserProfile disclosure, never by copying a memory row.

So every face is exercised from both sides of the pair:

- a write for Persona A is invisible to Persona B — the view, the summary
  and the scoped read all come back empty, while A's own reads return the
  memory;
- both legs isolate: the same persona with a different user is a different
  memory space;
- the Recorder handed B's summary cannot even name A's memory (the supersede
  pointer is refused without disclosure), and the write face refuses a
  cross-persona supersede with exactly the refusal a never-existed id gets —
  same code, same message, no existence disclosed (DEC-…5ba74efc.115 F3;
  BF-05 §29).
"""

from __future__ import annotations

import sqlite3

from elc.conversation import SqliteConversationStore
from elc.platform.types import (
    DomainErrorCode,
    Err,
    Ok,
    RelationshipMemoryId,
    TurnId,
    UserId,
)
from elc.relationship import (
    MemoryStatus,
    RelationshipController,
    RelationshipRecorder,
)
from elc.relationship.store import SqliteRelationshipStore

from .conftest import (
    PERSONA_A,
    PERSONA_B,
    REL_USER,
    memory_candidate,
    memory_proposal,
    memory_rows,
    open_conversation_for,
    record_turn,
    speak,
    turn_slice,
)

OTHER_USER = UserId("user-2")


def _write_for_persona_a(
    store: SqliteConversationStore,
    recorder: RelationshipRecorder,
    controller: RelationshipController,
) -> RelationshipMemoryId:
    """One real chain write for (PERSONA_A, REL_USER)."""

    conversation = open_conversation_for(store, "conv-iso-a", PERSONA_A)
    turn_id = speak(store, conversation, "cm-1", "I live in Berlin.")
    slice_ = turn_slice(store, turn_id)
    summary = controller.get_existing_summary(PERSONA_A, REL_USER)
    assert isinstance(summary, Ok)
    outcome = record_turn(
        recorder,
        slice_,
        summary.value,
        memory_candidate("The user lives in Berlin."),
    )
    assert outcome.refusals == ()
    written = controller.propose_memory(outcome.proposals[0])
    assert isinstance(written, Ok), written
    return written.value


def test_a_memory_is_invisible_to_another_persona(
    store: SqliteConversationStore,
    recorder: RelationshipRecorder,
    relationship_controller: RelationshipController,
    relationship_store: SqliteRelationshipStore,
    db: sqlite3.Connection,
) -> None:
    memory_id = _write_for_persona_a(store, recorder, relationship_controller)

    # Persona B over the same user: nothing at all — not the row, not its id.
    view_b = relationship_controller.get_relationship_view(PERSONA_B, REL_USER)
    assert isinstance(view_b, Ok)
    assert view_b.value.active_memories == ()
    summary_b = relationship_controller.get_existing_summary(PERSONA_B, REL_USER)
    assert isinstance(summary_b, Ok)
    assert summary_b.value.memories == ()
    assert summary_b.value.find(memory_id) is None
    scoped_b = relationship_store.get_scoped_memory(
        PERSONA_B, REL_USER, memory_id
    )
    assert isinstance(scoped_b, Ok) and scoped_b.value is None

    # Persona A's own reads return exactly that memory.
    view_a = relationship_controller.get_relationship_view(PERSONA_A, REL_USER)
    assert isinstance(view_a, Ok)
    assert [m.relationship_memory_id for m in view_a.value.active_memories] == [
        memory_id
    ]
    summary_a = relationship_controller.get_existing_summary(PERSONA_A, REL_USER)
    assert isinstance(summary_a, Ok)
    assert [e.relationship_memory_id for e in summary_a.value.memories] == [
        memory_id
    ]
    scoped_a = relationship_store.get_scoped_memory(
        PERSONA_A, REL_USER, memory_id
    )
    assert isinstance(scoped_a, Ok) and scoped_a.value is not None
    assert scoped_a.value.canonical_content == "The user lives in Berlin."
    assert scoped_a.value.status is MemoryStatus.ACTIVE
    assert len(memory_rows(db)) == 1


def test_the_user_leg_of_the_unit_isolates_too(
    relationship_controller: RelationshipController,
    relationship_store: SqliteRelationshipStore,
    store: SqliteConversationStore,
) -> None:
    """§5's unit has two legs: the same persona over another user is another
    memory space."""

    conversation = open_conversation_for(store, "conv-iso-user", PERSONA_A)
    turn_id = speak(store, conversation, "cm-1", "I live in Berlin.")
    written = relationship_controller.propose_memory(
        memory_proposal("The user lives in Berlin.", source_turn_id=turn_id)
    )
    assert isinstance(written, Ok)

    view = relationship_controller.get_relationship_view(PERSONA_A, OTHER_USER)
    assert isinstance(view, Ok)
    assert view.value.active_memories == ()
    summary = relationship_controller.get_existing_summary(PERSONA_A, OTHER_USER)
    assert isinstance(summary, Ok)
    assert summary.value.memories == ()
    scoped = relationship_store.get_scoped_memory(
        PERSONA_A, OTHER_USER, written.value
    )
    assert isinstance(scoped, Ok) and scoped.value is None


def test_the_recorder_cannot_reach_another_personas_memory(
    store: SqliteConversationStore,
    recorder: RelationshipRecorder,
    relationship_controller: RelationshipController,
) -> None:
    """The real rows this time: Persona B's summary simply does not contain
    Persona A's memory, so the pointer is refused without disclosure."""

    memory_id = _write_for_persona_a(store, recorder, relationship_controller)
    conversation = open_conversation_for(store, "conv-iso-b", PERSONA_B)
    b_turn = speak(store, conversation, "cm-1", "I live in Hamburg.")
    slice_ = turn_slice(store, b_turn)

    summary_b = relationship_controller.get_existing_summary(PERSONA_B, REL_USER)
    assert isinstance(summary_b, Ok)
    refused = record_turn(
        recorder,
        slice_,
        summary_b.value,
        memory_candidate("The user lives in Hamburg.", supersedes=memory_id),
    )
    assert refused.proposals == ()
    assert refused.refusals[0].reason == "SUPERSEDE_TARGET_OUT_OF_SCOPE"

    # Persona A's own summary does contain it, so the same pointer is legal
    # there.
    summary_a = relationship_controller.get_existing_summary(PERSONA_A, REL_USER)
    assert isinstance(summary_a, Ok)
    accepted = record_turn(
        recorder,
        slice_,
        summary_a.value,
        memory_candidate("The user lives in Hamburg.", supersedes=memory_id),
    )
    assert accepted.refusals == ()
    assert accepted.proposals[0].supersedes_memory_id == memory_id


def test_a_cross_persona_supersede_is_indistinguishable_from_a_missing_target(
    store: SqliteConversationStore,
    recorder: RelationshipRecorder,
    relationship_controller: RelationshipController,
    db: sqlite3.Connection,
) -> None:
    """DEC-…5ba74efc.115 F3 / BF-05 §29: the write face reads the supersede
    target *inside* the writing scope, so another persona's row is not
    "refused as foreign" — it is not there at all. The two probes below come
    back with the same code and the same message, word for word, and the
    other persona's row is untouched."""

    memory_id = _write_for_persona_a(store, recorder, relationship_controller)
    conversation = open_conversation_for(store, "conv-iso-c", PERSONA_B)
    b_turn = speak(store, conversation, "cm-1", "I live in Hamburg.")
    before = memory_rows(db)

    # Probe 1: the pointer names Persona A's row (it exists — elsewhere).
    cross_scope = relationship_controller.propose_memory(
        memory_proposal(
            "The user lives in Hamburg.",
            persona_id=PERSONA_B,
            source_turn_id=TurnId(b_turn),
            supersedes_memory_id=memory_id,
        )
    )
    # Probe 2: the pointer names a row that never existed at all.
    never_existed = relationship_controller.propose_memory(
        memory_proposal(
            "The user lives in Hamburg.",
            persona_id=PERSONA_B,
            source_turn_id=TurnId(b_turn),
            supersedes_memory_id=RelationshipMemoryId("rm-never-existed"),
        )
    )

    assert isinstance(cross_scope, Err)
    assert isinstance(never_existed, Err)
    # One refusal, word for word: the caller cannot tell the two apart, so the
    # refusal never discloses that another persona's row is there.
    assert cross_scope.error.code is DomainErrorCode.VALIDATION_FAILED
    assert cross_scope.error.code is never_existed.error.code
    assert cross_scope.error.message == never_existed.error.message
    assert cross_scope.error.message == "supersede target not found"
    # The refusal never echoes the other persona's content (§29).
    assert "Berlin" not in cross_scope.error.message
    # Zero writes on either probe: the other persona's row is exactly as it
    # was.
    assert memory_rows(db) == before
