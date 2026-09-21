"""P4-1 ④ — the BF-05 sensitive-memory gate (VAL-…5ba74efc.72 ④).

BF-05 (``security_privacy_policy_v1.json`` → ``sensitive_memory_policy``)
and SECURITY_PRIVACY_DELETION_CONTRACT_v1.0.md §8:

    transcript storage ≠ long-term relationship-memory permission
    automatic_relationship_promotion  DENY
    explicit_user_persistence         ALLOW_AFTER_VALIDATION
    system_inference                  DENY_FOR_HIGH_SENSITIVITY

So the arms asserted here are:

- a **model-inferred high-sensitivity attribute** is denied — by the
  Recorder (it never becomes a proposal) and by the write face (a
  hand-assembled proposal cannot bypass the gate);
- a **user-stated high-sensitivity fact without explicit persistence
  permission** is denied too (no automatic promotion), while the user's own
  sentence stays in the transcript as user-authored content;
- **explicit persistence** allows the write after validation, and the row
  then carries the cross-column pair the schema's CHECK also demands;
- a PERSONAL memory is the ordinary §5 write flow, no extra permission.
"""

from __future__ import annotations

import sqlite3

import pytest

from elc.conversation import SqliteConversationStore
from elc.platform.types import DomainErrorCode, Err, Ok, TurnId
from elc.relationship import (
    ALLOW_AFTER_VALIDATION,
    DENY,
    MemoryProvenance,
    MemorySensitivityClass,
    PersistenceAuthorization,
    RelationshipController,
    RelationshipMemoryType,
    decide_persistence,
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

#: The BF-05 example class ("health, religion, political affiliation, …").
SENSITIVE_STATEMENT = "I have been treated for asthma since I was a child."
INFERRED_STATEMENT = "The user seems to be dealing with a health condition."


def test_the_gate_words_are_bf05s() -> None:
    assert (ALLOW_AFTER_VALIDATION, DENY) == ("ALLOW_AFTER_VALIDATION", "DENY")
    personal = decide_persistence(
        sensitivity_class=MemorySensitivityClass.PERSONAL,
        persistence_authorization=(
            PersistenceAuthorization.VALIDATED_DOMAIN_WRITE
        ),
        provenance=MemoryProvenance.USER_STATED_FACT,
    )
    assert personal.allowed and personal.decision == ALLOW_AFTER_VALIDATION
    inferred = decide_persistence(
        sensitivity_class=MemorySensitivityClass.HIGH_SENSITIVITY,
        persistence_authorization=(
            PersistenceAuthorization.USER_EXPLICIT_CONSENT
        ),
        provenance=MemoryProvenance.SYSTEM_INFERRED_FACT,
    )
    assert not inferred.allowed and inferred.decision == DENY


def test_a_model_inferred_high_sensitivity_attribute_is_denied_everywhere(
    store: SqliteConversationStore,
    recorder,
    relationship_controller: RelationshipController,
    db: sqlite3.Connection,
) -> None:
    """Both halves of the red line: the Recorder refuses to propose it, and
    the write face refuses it even when handed a hand-assembled proposal.
    The transcript keeps what the user said; the memory is not created."""

    conversation = open_conversation_for(store, "conv-sens-1", PERSONA_A)
    turn_id = speak(store, conversation, "cm-1", SENSITIVE_STATEMENT)
    deliver_reply(store, turn_id, conversation, "Thanks for telling me.")
    slice_ = turn_slice(store, turn_id)
    summary = relationship_controller.get_existing_summary(PERSONA_A, REL_USER)
    assert isinstance(summary, Ok)

    outcome = record_turn(
        recorder,
        slice_,
        summary.value,
        memory_candidate(
            INFERRED_STATEMENT,
            memory_type=RelationshipMemoryType.PERSONA_IMPRESSION,
            provenance=MemoryProvenance.SYSTEM_INFERRED_FACT,
            confidence=0.6,
            sensitivity_class=MemorySensitivityClass.HIGH_SENSITIVITY,
        ),
    )
    assert outcome.proposals == ()
    (refusal,) = outcome.refusals
    assert refusal.reason == "HIGH_SENSITIVITY_SYSTEM_INFERENCE"
    assert "DENY_FOR_HIGH_SENSITIVITY" in refusal.detail

    # A hand-assembled proposal claiming consent for an *inferred* attribute
    # cannot self-grant it (DOMAIN_MODEL §18.1).
    direct = relationship_controller.propose_memory(
        memory_proposal(
            INFERRED_STATEMENT,
            source_turn_id=turn_id,
            memory_type=RelationshipMemoryType.PERSONA_IMPRESSION,
            provenance=MemoryProvenance.SYSTEM_INFERRED_FACT,
            confidence=0.6,
            sensitivity_class=MemorySensitivityClass.HIGH_SENSITIVITY,
            persistence_authorization=(
                PersistenceAuthorization.USER_EXPLICIT_CONSENT
            ),
        )
    )
    assert isinstance(direct, Err)
    assert direct.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "DENY_FOR_HIGH_SENSITIVITY" in direct.error.message
    assert memory_rows(db) == []

    # transcript_storage = ALLOWED_AS_USER_AUTHORED_CONTENT: the user's own
    # sentence is in the transcript, exactly where it belongs.
    assert db.execute(
        "SELECT raw_content FROM user_turn WHERE turn_id = ?", (str(turn_id),)
    ).fetchone()[0] == SENSITIVE_STATEMENT


def test_a_user_stated_high_sensitivity_fact_without_consent_is_denied(
    store: SqliteConversationStore,
    relationship_controller: RelationshipController,
    db: sqlite3.Connection,
) -> None:
    """automatic_relationship_promotion = DENY: the user said it, the
    transcript keeps it, and nothing promotes it on its own."""

    conversation = open_conversation_for(store, "conv-sens-2", PERSONA_A)
    turn_id = speak(store, conversation, "cm-1", SENSITIVE_STATEMENT)
    del conversation

    proposal = memory_proposal(
        SENSITIVE_STATEMENT,
        source_turn_id=turn_id,
        sensitivity_class=MemorySensitivityClass.HIGH_SENSITIVITY,
    )
    assert validate_proposal(proposal) is None  # a legal proposal shape…
    refused = relationship_controller.propose_memory(proposal)
    assert isinstance(refused, Err)  # …that the gate still refuses
    assert "HIGH_SENSITIVITY_WITHOUT_EXPLICIT_CONSENT" in refused.error.message
    assert memory_rows(db) == []


def test_explicit_user_persistence_is_allowed_after_validation(
    store: SqliteConversationStore,
    relationship_controller: RelationshipController,
    db: sqlite3.Connection,
) -> None:
    """explicit_user_persistence = ALLOW_AFTER_VALIDATION, and the durable row
    carries the pair migration 0009's CHECK also demands."""

    conversation = open_conversation_for(store, "conv-sens-3", PERSONA_A)
    turn_id = speak(store, conversation, "cm-1", SENSITIVE_STATEMENT)
    del conversation

    written = relationship_controller.propose_memory(
        memory_proposal(
            SENSITIVE_STATEMENT,
            source_turn_id=turn_id,
            sensitivity_class=MemorySensitivityClass.HIGH_SENSITIVITY,
            persistence_authorization=(
                PersistenceAuthorization.USER_EXPLICIT_CONSENT
            ),
        )
    )
    assert isinstance(written, Ok), written
    (row,) = memory_rows(db)
    assert row[14] == "HIGH_SENSITIVITY"
    assert row[15] == "USER_EXPLICIT_CONSENT"


def test_the_schema_refuses_the_forbidden_pair_too(db: sqlite3.Connection) -> None:
    """Defence in depth: even if a row somehow reached the store, migration
    0009's cross-column CHECK (HIGH_SENSITIVITY ⇒ USER_EXPLICIT_CONSENT)
    makes the denied combination unwritable."""

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO relationship_memory ("
            " relationship_memory_id, persona_id, user_id, memory_type,"
            " provenance, canonical_content, source_turn_id, status,"
            " source_turn_ids, provenance_refs, confidence,"
            " supersedes_memory_id, recorder_version, validator_version,"
            " sensitivity_class, persistence_authorization,"
            " created_at, updated_at"
            ") VALUES ('rm-x', 'persona-a', 'user-1', 'USER_STATED_FACT',"
            " 'USER_STATED_FACT', 'x', NULL, 'ACTIVE', '[]', '[]', NULL,"
            " NULL, 'v0', NULL, 'HIGH_SENSITIVITY', 'VALIDATED_DOMAIN_WRITE',"
            " '2026-09-21T00:00:00+00:00', '2026-09-21T00:00:00+00:00')"
        )


def test_a_personal_memory_needs_no_extra_permission(
    store: SqliteConversationStore,
    relationship_controller: RelationshipController,
    db: sqlite3.Connection,
) -> None:
    conversation = open_conversation_for(store, "conv-sens-4", PERSONA_A)
    turn_id: TurnId = speak(store, conversation, "cm-1", "I love rainy Tuesdays.")

    written = relationship_controller.propose_memory(
        memory_proposal("The user loves rainy Tuesdays.", source_turn_id=turn_id)
    )
    assert isinstance(written, Ok)
    (row,) = memory_rows(db)
    assert (row[14], row[15]) == ("PERSONAL", "VALIDATED_DOMAIN_WRITE")
