"""P4-1 ② — validate / dedupe / append-first supersede (VAL-…72 ②).

docs/DOMAIN_MODEL.md §5's write flow, end to end and durable:

    Relationship Recorder proposal
    → Relationship Domain validate/dedupe
    → canonical Relationship Memory

The chain is driven for real: a canonical turn slice goes through the
Recorder, and the proposal it produces goes through the controller into
``relationship_memory``. The pins here are the write-flow properties the
task names — validate before any write, a deterministic dedupe rule,
append-first supersede (the old row is never rewritten in place and never
deleted), a real ``recorder_version`` in every durable row (review F6), and
idempotent replay of the same write.
"""

from __future__ import annotations

import sqlite3

import pytest

from elc.conversation import SqliteConversationStore
from elc.platform.types import (
    DomainErrorCode,
    Err,
    Ok,
    PersonaId,
    RelationshipMemoryId,
    TurnId,
)
from elc.relationship import (
    RELATIONSHIP_RECORDER_VERSION,
    RELATIONSHIP_VALIDATOR_VERSION,
    MemoryProvenance,
    MemoryStatus,
    RelationshipController,
    RelationshipMemoryProposal,
    RelationshipMemoryType,
    SqliteRelationshipStore,
    normalize_memory_content,
    validate_proposal,
)

from .conftest import (
    PERSONA_A,
    REL_USER,
    deliver_reply,
    memory_candidate,
    memory_proposal,
    memory_rows,
    open_conversation_for,
    record_turn,
    speak,
    turn_slice,
)


@pytest.fixture()
def turns(store: SqliteConversationStore) -> tuple[TurnId, TurnId]:
    """Two real user turns of one persona's conversation (the durable ids a
    proposal's provenance binds to)."""

    conversation = open_conversation_for(store, "conv-write", PERSONA_A)
    first = speak(store, conversation, "cm-1", "I live in Berlin.")
    deliver_reply(store, first, conversation, "Berlin is a big city.")
    second = speak(store, conversation, "cm-2", "I moved to Hamburg last month.")
    return first, second


def test_the_write_flow_is_recorder_then_validate_then_canonical(
    store: SqliteConversationStore,
    recorder,
    relationship_controller: RelationshipController,
    relationship_store: SqliteRelationshipStore,
    turns: tuple[TurnId, TurnId],
    db: sqlite3.Connection,
) -> None:
    first, _ = turns
    slice_ = turn_slice(store, first)
    summary = relationship_controller.get_existing_summary(PERSONA_A, REL_USER)
    assert isinstance(summary, Ok) and summary.value.memories == ()

    outcome = record_turn(
        recorder,
        slice_,
        summary.value,
        memory_candidate("The user lives in Berlin."),
    )
    assert outcome.refusals == ()
    (proposal,) = outcome.proposals

    written = relationship_controller.propose_memory(proposal)
    assert isinstance(written, Ok), written

    (row,) = memory_rows(db)
    (
        memory_id,
        persona_id,
        user_id,
        memory_type,
        provenance,
        content,
        source_turn_id,
        status,
        source_turn_ids,
        provenance_refs,
        confidence,
        supersedes,
        recorder_version,
        validator_version,
        sensitivity,
        authorization,
    ) = row
    assert str(memory_id) == str(written.value)
    assert (persona_id, user_id) == (str(PERSONA_A), str(REL_USER))
    assert memory_type == RelationshipMemoryType.USER_STATED_FACT.value
    assert provenance == MemoryProvenance.USER_STATED_FACT.value
    assert content == "The user lives in Berlin."
    assert source_turn_id == str(first)
    assert status == MemoryStatus.ACTIVE.value
    assert source_turn_ids == f'["{first}"]'
    assert str(slice_.user_turn.user_turn_id) in provenance_refs
    assert confidence is None
    assert supersedes is None
    # F6: the Recorder's real version, never ''.
    assert recorder_version == RELATIONSHIP_RECORDER_VERSION != ""
    # The P4-1 path is the TRUSTED_AUTHORITY domain-validated write, so the
    # model-assisted validator version stays NULL on purpose (review F6).
    assert validator_version is None
    assert sensitivity == "PERSONAL"
    assert authorization == "VALIDATED_DOMAIN_WRITE"

    view = relationship_controller.get_relationship_view(PERSONA_A, REL_USER)
    assert isinstance(view, Ok)
    assert [m.relationship_memory_id for m in view.value.active_memories] == [
        written.value
    ]


def test_a_model_assisted_validator_version_is_recorded_when_declared(
    relationship_store: SqliteRelationshipStore,
    turns: tuple[TurnId, TurnId],
    db: sqlite3.Connection,
) -> None:
    """The column is real: an assembly that runs a model-assisted validator
    records it (the default NULL is the trusted-path semantics, not a gap)."""

    controller = RelationshipController(
        relationship_store, validator_version="stub-validator-v0"
    )
    written = controller.propose_memory(
        memory_proposal("The user lives in Berlin.", source_turn_id=turns[0])
    )
    assert isinstance(written, Ok)
    assert memory_rows(db)[0][13] == "stub-validator-v0"
    assert RELATIONSHIP_VALIDATOR_VERSION == "v0"


def test_each_validation_rule_refuses_before_the_store(
    relationship_controller: RelationshipController,
    turns: tuple[TurnId, TurnId],
    db: sqlite3.Connection,
) -> None:
    """The §5 validate leg: every refusal is an Err and nothing is written."""

    first, _ = turns
    bad: list[tuple[str, RelationshipMemoryProposal]] = [
        (
            "empty content",
            memory_proposal("   ", source_turn_id=first),
        ),
        (
            "empty recorder_version",
            memory_proposal(
                "The user lives in Berlin.",
                source_turn_id=first,
                recorder_version="",
            ),
        ),
        (
            "user-stated fact without the real user turn in its refs",
            memory_proposal(
                "The user lives in Berlin.",
                source_turn_id=None,
                provenance_refs=(),
            ),
        ),
        (
            "user-stated type with an impression provenance",
            memory_proposal(
                "The user lives in Berlin.",
                source_turn_id=first,
                provenance=MemoryProvenance.PERSONA_IMPRESSION,
            ),
        ),
        (
            "confidence on a user statement",
            memory_proposal(
                "The user lives in Berlin.", source_turn_id=first, confidence=0.5
            ),
        ),
        (
            "inference without its confidence",
            memory_proposal(
                "The user probably lives in Berlin.",
                source_turn_id=first,
                provenance=MemoryProvenance.SYSTEM_INFERRED_FACT,
            ),
        ),
        (
            "empty scope leg",
            memory_proposal(
                "The user lives in Berlin.",
                source_turn_id=first,
                persona_id=PersonaId(""),
            ),
        ),
    ]
    for label, proposal in bad:
        assert validate_proposal(proposal) is not None, label
        refused = relationship_controller.propose_memory(proposal)
        assert isinstance(refused, Err), label
        assert refused.error.code is DomainErrorCode.VALIDATION_FAILED, label
        assert db.execute(
            "SELECT COUNT(*) FROM relationship_memory"
        ).fetchone()[0] == 0, label


def test_dedupe_is_normalized_exact_matching(
    relationship_controller: RelationshipController,
    turns: tuple[TurnId, TurnId],
    db: sqlite3.Connection,
) -> None:
    """The dedupe rule: same (persona, user, memory_type) + equal content
    after normalization = the same memory — the durable row stays canonical
    and nothing is appended for a re-statement."""

    first, second = turns
    written = relationship_controller.propose_memory(
        memory_proposal("The user lives in Berlin.", source_turn_id=first)
    )
    assert isinstance(written, Ok)

    # A second turn re-states it with different case and trailing punctuation.
    again = relationship_controller.propose_memory(
        memory_proposal(
            "  the user lives in berlin!  ", source_turn_id=second
        )
    )
    assert isinstance(again, Ok)
    assert again.value == written.value
    assert len(memory_rows(db)) == 1

    # A *different* statement of the same type is a second memory, not a
    # correction — the write face never infers supersede intent.
    other = relationship_controller.propose_memory(
        memory_proposal("The user works as a nurse.", source_turn_id=second)
    )
    assert isinstance(other, Ok)
    assert other.value != written.value
    assert len(memory_rows(db)) == 2
    assert normalize_memory_content("I live in Berlin!") == "i live in berlin"


def test_supersede_is_append_first(
    relationship_controller: RelationshipController,
    relationship_store: SqliteRelationshipStore,
    turns: tuple[TurnId, TurnId],
    db: sqlite3.Connection,
) -> None:
    """§1.3 append-first: the replacement is appended and the corrected row
    becomes SUPERSEDED — never rewritten in place, never deleted."""

    first, second = turns
    original = relationship_controller.propose_memory(
        memory_proposal("The user lives in Berlin.", source_turn_id=first)
    )
    assert isinstance(original, Ok)

    replacement = relationship_controller.propose_memory(
        memory_proposal(
            "The user lives in Hamburg.",
            source_turn_id=second,
            supersedes_memory_id=original.value,
        )
    )
    assert isinstance(replacement, Ok)
    assert replacement.value != original.value

    rows = {str(row[0]): row for row in memory_rows(db)}
    assert len(rows) == 2  # append, never rewrite
    old = rows[str(original.value)]
    new = rows[str(replacement.value)]
    assert old[7] == MemoryStatus.SUPERSEDED.value
    assert new[7] == MemoryStatus.ACTIVE.value
    assert new[6] == str(second)
    assert old[5] == "The user lives in Berlin."
    assert new[11] == str(original.value)

    # The superseded row is still readable inside its own scope; it is gone
    # from the view (ACTIVE only) and from the Recorder's summary.
    kept = relationship_store.get_scoped_memory(
        PERSONA_A, REL_USER, original.value
    )
    assert isinstance(kept, Ok) and kept.value is not None
    assert kept.value.status is MemoryStatus.SUPERSEDED
    view = relationship_controller.get_relationship_view(PERSONA_A, REL_USER)
    assert isinstance(view, Ok)
    assert [m.relationship_memory_id for m in view.value.active_memories] == [
        replacement.value
    ]


def test_supersede_refusals_never_rewrite_history(
    relationship_controller: RelationshipController,
    turns: tuple[TurnId, TurnId],
    db: sqlite3.Connection,
) -> None:
    first, second = turns
    original = relationship_controller.propose_memory(
        memory_proposal("The user lives in Berlin.", source_turn_id=first)
    )
    assert isinstance(original, Ok)
    before = memory_rows(db)

    missing = relationship_controller.propose_memory(
        memory_proposal(
            "The user lives in Hamburg.",
            source_turn_id=second,
            supersedes_memory_id=RelationshipMemoryId("rm-does-not-exist"),
        )
    )
    assert isinstance(missing, Err)
    assert missing.error.code is DomainErrorCode.VALIDATION_FAILED

    wrong_type = relationship_controller.propose_memory(
        memory_proposal(
            "The user promised to practise daily.",
            source_turn_id=second,
            memory_type=RelationshipMemoryType.PROMISE,
            provenance=MemoryProvenance.USER_STATED_FACT,
            supersedes_memory_id=original.value,
        )
    )
    assert isinstance(wrong_type, Err)
    assert wrong_type.error.code is DomainErrorCode.VALIDATION_FAILED

    # ... and a declared supersede that changes nothing (same text) is an
    # idempotent no-op rather than a second row.
    same = relationship_controller.propose_memory(
        memory_proposal(
            "The user lives in Berlin.",
            source_turn_id=second,
            supersedes_memory_id=original.value,
        )
    )
    assert isinstance(same, Ok)
    assert same.value == original.value
    assert memory_rows(db) == before


def test_an_idempotent_replay_writes_nothing_and_a_changed_payload_conflicts(
    relationship_controller: RelationshipController,
    turns: tuple[TurnId, TurnId],
    db: sqlite3.Connection,
) -> None:
    """The memory id is deterministic (DATA_MODEL §1.2), so a retry of the
    same write replays; a *different* payload under the same id is a
    CONFLICT rather than a silent overwrite."""

    first, _ = turns
    proposal = memory_proposal("The user lives in Berlin.", source_turn_id=first)
    first_write = relationship_controller.propose_memory(proposal)
    assert isinstance(first_write, Ok)
    replay = relationship_controller.propose_memory(proposal)
    assert isinstance(replay, Ok)
    assert replay.value == first_write.value
    assert len(memory_rows(db)) == 1
    assert memory_rows(db)[0][12] == RELATIONSHIP_RECORDER_VERSION

    # Same id (scope, type, normalized content, turn), different declared
    # payload: the same write carried a different provenance ref set.
    conflicting = relationship_controller.propose_memory(
        memory_proposal(
            "The user lives in Berlin.",
            source_turn_id=first,
            provenance_refs=(str(first), "ref-from-an-earlier-draft"),
        )
    )
    assert isinstance(conflicting, Err)
    assert conflicting.error.code is DomainErrorCode.CONFLICT
    assert len(memory_rows(db)) == 1


def test_recorder_version_is_filled_in_every_durable_row(
    store: SqliteConversationStore,
    recorder,
    relationship_controller: RelationshipController,
    relationship_store: SqliteRelationshipStore,
    turns: tuple[TurnId, TurnId],
    db: sqlite3.Connection,
) -> None:
    """Review F6 across the whole chain: no row is ever written with an empty
    recorder_version, and the validator's own identity is the pure module's."""

    first, second = turns
    slice_ = turn_slice(store, first)
    summary = relationship_controller.get_existing_summary(PERSONA_A, REL_USER)
    assert isinstance(summary, Ok)
    outcome = record_turn(
        recorder,
        slice_,
        summary.value,
        memory_candidate("The user lives in Berlin."),
        memory_candidate("The user works as a nurse."),
    )
    assert outcome.refusals == ()
    for proposal in outcome.proposals:
        assert relationship_controller.propose_memory(proposal) is not None
    assert relationship_controller.propose_memory(
        memory_proposal("The user lives in Hamburg.", source_turn_id=second)
    )
    rows = memory_rows(db)
    assert len(rows) == 3
    assert all(str(row[12]) == RELATIONSHIP_RECORDER_VERSION for row in rows)
    assert all(str(row[12]) != "" for row in rows)


def test_the_frozen_phase0_shapes_are_pointers_not_logic(
    relationship_controller: RelationshipController,
) -> None:
    """P4-1 keeps the frozen protocol shapes honest: ``supersede_memory``
    carries no recorder identity (the row's recorder_version is NOT NULL) and
    ``get_memory`` carries no Persona×User leg — both raise with a pointer."""

    with pytest.raises(NotImplementedError) as supersede:
        relationship_controller.supersede_memory(
            RelationshipMemoryId("rm-1"), "replacement"
        )
    assert "supersedes_memory_id" in str(supersede.value)

    with pytest.raises(NotImplementedError) as unscoped:
        relationship_controller.get_memory(RelationshipMemoryId("rm-1"))
    assert "get_scoped_memory" in str(unscoped.value)
