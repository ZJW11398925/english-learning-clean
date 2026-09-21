"""P4-1 ① — the Relationship Recorder (VAL-…5ba74efc.72 ⑤ + IP §4 Acceptance①).

The Recorder is the §5 write flow's first leg: it reads one
CanonicalTurnSlice and the same-persona summary, and returns proposals plus
the refusals that explain every candidate it would not propose. Nothing here
writes durable memory — that is the controller's face
(tests/phase4/test_p4_1_write_chain.py).

What is asserted here is the red-line behaviour the P4-G1 gate frames:

- a **command turn** (TEACHING_REQUEST / TEACHING_RESPONSE: a typed payload
  and an empty utterance) never becomes USER_STATED_FACT /
  CONVERSATION_PREFERENCE / SHARED_EVENT;
- **undelivered assistant output never enters Relationship**: a pair/persona
  memory needs the turn's assistant side canonical, and a cited id the
  transcript never kept is refused;
- a **USER_STATED_FACT needs a real user turn** (BF-05 §7);
- a **supersede pointer outside the same-persona summary** is refused, and
  the refusal does not disclose whether the memory exists elsewhere (§29);
- the Recorder **fails closed** when the durable classification cannot be
  read, and writes nothing at all.
"""

from __future__ import annotations

import sqlite3

from elc.conversation import SqliteConversationStore
from elc.platform.types import (
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    RelationshipMemoryId,
    TurnId,
)
from elc.relationship import (
    RELATIONSHIP_RECORDER_VERSION,
    CommandTurnClassifier,
    MemoryProvenance,
    MemorySensitivityClass,
    MemoryStatus,
    PersistenceAuthorization,
    RelationshipMemoryRefusal,
    RelationshipMemorySummaryEntry,
    RelationshipMemoryType,
    RelationshipRecorder,
    RelationshipRecorderKey,
    RelationshipRecorderOutcome,
    SamePersonaExistingRelationshipSummary,
    command_turn_memory_refusal,
)
from elc.runtime.controller import ConversationCoordinator

from .conftest import (
    CONV,
    PERSONA_A,
    PERSONA_B,
    REL_USER,
    deliver_reply,
    memory_candidate,
    newest_command_turn_slice,
    open_conversation_for,
    open_moment,
    record_turn,
    speak,
    turn_slice,
)


def _summary(
    *entries: RelationshipMemorySummaryEntry, persona_id=PERSONA_A
) -> SamePersonaExistingRelationshipSummary:
    return SamePersonaExistingRelationshipSummary(
        persona_id=persona_id, user_id=REL_USER, memories=entries
    )


def _refusal(
    outcome: RelationshipRecorderOutcome, reason: str
) -> RelationshipMemoryRefusal:
    matches = [item for item in outcome.refusals if item.reason == reason]
    assert len(matches) == 1, [item.reason for item in outcome.refusals]
    return matches[0]


def test_an_ordinary_turn_yields_a_traceable_proposal(
    store: SqliteConversationStore,
    recorder: RelationshipRecorder,
    db: sqlite3.Connection,
) -> None:
    """The positive control: a user statement on a delivered turn becomes a
    proposal bound to the summary's scope, carrying the slice's own ids and
    the Recorder's real version (review F6)."""

    conversation = open_conversation_for(store, "conv-rel-1", PERSONA_A)
    turn_id = speak(store, conversation, "cm-1", "I have been learning Japanese.")
    deliver_reply(store, turn_id, conversation, "That takes patience!")
    slice_ = turn_slice(store, turn_id)

    outcome = record_turn(
        recorder,
        slice_,
        _summary(),
        memory_candidate(
            "The user has been learning Japanese.",
            cited=(str(slice_.user_turn.user_turn_id),),
        ),
    )

    assert outcome.refusals == ()
    (proposal,) = outcome.proposals
    assert proposal.persona_id == PERSONA_A
    assert proposal.user_id == REL_USER
    assert proposal.source_turn_id == turn_id
    assert proposal.source_turn_ids == (turn_id,)
    assert str(slice_.user_turn.user_turn_id) in proposal.provenance_refs
    assert proposal.recorder_version == RELATIONSHIP_RECORDER_VERSION != ""
    assert proposal.confidence is None
    assert proposal.sensitivity_class is MemorySensitivityClass.PERSONAL
    assert (
        proposal.persistence_authorization
        is PersistenceAuthorization.VALIDATED_DOMAIN_WRITE
    )
    # The Recorder proposes; it never writes (§18 proposal-only).
    assert db.execute("SELECT COUNT(*) FROM relationship_memory").fetchone()[0] == 0


def test_a_command_turn_says_nothing(
    coordinator: ConversationCoordinator,
    store: SqliteConversationStore,
    recorder: RelationshipRecorder,
    db: sqlite3.Connection,
) -> None:
    """VAL-…72 ⑤: a real TEACHING_REQUEST turn — typed payload, empty
    utterance — never becomes a user statement, a preference or a shared
    event, however the candidate is declared."""

    open_moment(coordinator, "cm-cmd")
    command_slice = newest_command_turn_slice(store, db, CONV)
    assert command_slice.user_turn.raw_content == ""

    outcome = record_turn(
        recorder,
        command_slice,
        _summary(),
        memory_candidate(
            "The user said they like the persona.",
            memory_type=RelationshipMemoryType.USER_STATED_FACT,
        ),
        memory_candidate(
            "The user prefers short lessons.",
            memory_type=RelationshipMemoryType.CONVERSATION_PREFERENCE,
        ),
        memory_candidate(
            "They met on a rainy Tuesday.",
            memory_type=RelationshipMemoryType.SHARED_EVENT,
        ),
    )

    assert outcome.proposals == ()
    assert [item.memory_type for item in outcome.refusals] == [
        RelationshipMemoryType.USER_STATED_FACT.value,
        RelationshipMemoryType.CONVERSATION_PREFERENCE.value,
        RelationshipMemoryType.SHARED_EVENT.value,
    ]
    assert [item.candidate_index for item in outcome.refusals] == [1, 2, 3]
    for item in outcome.refusals:
        assert item.reason == "COMMAND_TURN_SAYS_NOTHING"
        assert "command turn" in item.detail


def test_a_user_stated_fact_needs_a_real_user_turn(
    store: SqliteConversationStore, recorder: RelationshipRecorder
) -> None:
    """BF-05 §7: the claim "the user said this" cannot rest on silence."""

    conversation = open_conversation_for(store, "conv-rel-2", PERSONA_A)
    turn_id = speak(store, conversation, "cm-silent", "")
    slice_ = turn_slice(store, turn_id)
    # The turn is silence, not a command: the durable classifier says so.
    classified = store.is_command_payload_turn(turn_id)
    assert isinstance(classified, Ok) and classified.value is False

    outcome = record_turn(
        recorder, slice_, _summary(), memory_candidate("The user likes jazz.")
    )

    assert outcome.proposals == ()
    refusal = _refusal(outcome, "USER_STATED_FACT_WITHOUT_REAL_USER_TURN")
    assert "真实 UserTurn provenance" in refusal.detail


def test_undelivered_assistant_output_never_enters_relationship(
    store: SqliteConversationStore, recorder: RelationshipRecorder
) -> None:
    """IP §4 Acceptance①, both arms: a pair memory needs a canonical
    assistant side, and a cited id the transcript never kept is refused."""

    conversation = open_conversation_for(store, "conv-rel-3", PERSONA_A)
    turn_id = speak(store, conversation, "cm-1", "Do you remember our walk?")
    slice_ = turn_slice(store, turn_id)
    assert slice_.assistant_turn is None  # nothing delivered, nothing canonical

    outcome = record_turn(
        recorder,
        slice_,
        _summary(),
        memory_candidate(
            "They took a long walk together.",
            memory_type=RelationshipMemoryType.SHARED_EVENT,
        ),
    )
    assert outcome.proposals == ()
    assert "IP §4 Acceptance①" in _refusal(
        outcome, "ASSISTANT_OUTPUT_NOT_CANONICAL"
    ).detail

    # A citation of provider output that was never canonicalized is refused
    # as an unresolvable ref — the draft never became a durable id.
    cited = record_turn(
        recorder,
        slice_,
        _summary(),
        memory_candidate(
            "The user has a cat called Momo.", cited=("at-never-delivered",)
        ),
    )
    assert cited.proposals == ()
    assert "at-never-delivered" in _refusal(
        cited, "PROVENANCE_REF_NOT_IN_THE_SLICE"
    ).detail

    # Positive control: once the reply is really delivered the same candidate
    # passes, and its refs name the canonical assistant turn.
    assistant_id = deliver_reply(store, turn_id, conversation, "I remember it well.")
    delivered = record_turn(
        recorder,
        turn_slice(store, turn_id),
        _summary(),
        memory_candidate(
            "They took a long walk together.",
            memory_type=RelationshipMemoryType.SHARED_EVENT,
            provenance=MemoryProvenance.PERSONA_IMPRESSION,
        ),
    )
    assert delivered.refusals == ()
    (proposal,) = delivered.proposals
    assert str(assistant_id) in proposal.provenance_refs


def test_a_supersede_pointer_outside_the_scope_is_refused_without_disclosure(
    store: SqliteConversationStore, recorder: RelationshipRecorder
) -> None:
    """DOMAIN_MODEL §17 / BF-05 §29: another persona's memory is not visible
    here — the refusal does not even say whether the id exists."""

    foreign = RelationshipMemoryId("rm-belongs-to-persona-b")
    conversation = open_conversation_for(store, "conv-rel-4", PERSONA_A)
    turn_id = speak(store, conversation, "cm-1", "Actually, I moved to Hamburg.")
    slice_ = turn_slice(store, turn_id)

    refused = record_turn(
        recorder,
        slice_,
        _summary(),
        memory_candidate("The user lives in Hamburg.", supersedes=foreign),
    )
    assert refused.proposals == ()
    refusal = _refusal(refused, "SUPERSEDE_TARGET_OUT_OF_SCOPE")
    assert "not part of this persona's existing relationship summary" in (
        refusal.detail
    )
    assert "without saying whether it exists" in refusal.detail
    # The refusal echoes the caller's own argument and nothing more: it never
    # claims the memory exists for someone else (§29 — no leak, not even
    # existence).
    assert "belongs to another" not in refusal.detail

    # Positive control: with the memory in this persona's own summary the
    # pointer travels on the proposal.
    in_scope = _summary(
        RelationshipMemorySummaryEntry(
            relationship_memory_id=foreign,
            memory_type=RelationshipMemoryType.USER_STATED_FACT,
            provenance=MemoryProvenance.USER_STATED_FACT,
            canonical_content="The user lives in Berlin.",
            status=MemoryStatus.ACTIVE,
        )
    )
    accepted = record_turn(
        recorder,
        slice_,
        in_scope,
        memory_candidate("The user lives in Hamburg.", supersedes=foreign),
    )
    assert accepted.refusals == ()
    assert accepted.proposals[0].supersedes_memory_id == foreign


def test_the_scope_comes_from_the_summary(
    store: SqliteConversationStore, recorder: RelationshipRecorder
) -> None:
    """The slice knows its conversation but not its Persona×User pair (§5
    unit); the pair travels with the summary, and the proposal binds to it."""

    conversation = open_conversation_for(store, "conv-rel-5", PERSONA_B)
    turn_id = speak(store, conversation, "cm-1", "Hello again.")
    slice_ = turn_slice(store, turn_id)

    outcome = record_turn(
        recorder,
        slice_,
        _summary(persona_id=PERSONA_B),
        memory_candidate("The user greets the persona warmly."),
    )
    assert outcome.refusals == ()
    assert outcome.proposals[0].persona_id == PERSONA_B


class _BrokenClassifier:
    """A durable classifier that cannot answer (the fail-closed arm)."""

    def is_command_payload_turn(self, turn_id: TurnId):
        del turn_id
        return Err(
            DomainError(
                code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                message="app.db unavailable",
            )
        )


def test_the_recorder_fails_closed_when_the_classifier_cannot_answer(
    store: SqliteConversationStore, db: sqlite3.Connection
) -> None:
    conversation = open_conversation_for(store, "conv-rel-6", PERSONA_A)
    turn_id = speak(store, conversation, "cm-1", "I love rainy days.")
    slice_ = turn_slice(store, turn_id)

    recorder = RelationshipRecorder(_BrokenClassifier())
    outcome = recorder.record_turn(
        turn=slice_,
        existing=_summary(),
        key=RelationshipRecorderKey(
            candidates=(memory_candidate("The user loves rainy days."),)
        ),
    )
    assert outcome.proposals == ()
    assert "app.db unavailable" in _refusal(
        outcome, "COMMAND_TURN_CLASSIFICATION_UNAVAILABLE"
    ).detail
    assert db.execute("SELECT COUNT(*) FROM relationship_memory").fetchone()[0] == 0


def test_the_classifier_refusal_implies_zero_proposals(
    store: SqliteConversationStore,
) -> None:
    """The premise the CP4 retry rule reads (P4-4 review F-P44-2).

    ``RelationshipProjectionExecutor`` turns the
    ``COMMAND_TURN_CLASSIFICATION_UNAVAILABLE`` refusal into a retryable
    ``Err``, and that rule rests on an implication: the word can only appear
    in an outcome that proposes *nothing* — so leaving the job retryable can
    never hide a proposal that was made anyway. The implication is the
    classifier arm's own doing (it returns before any candidate is judged,
    one refusal per candidate); it is pinned here, beside that arm, instead
    of being left implicit at its consumer.
    """

    conversation = open_conversation_for(store, "conv-rel-6b", PERSONA_A)
    turn_id = speak(store, conversation, "cm-1", "I love rainy days.")
    slice_ = turn_slice(store, turn_id)

    recorder = RelationshipRecorder(_BrokenClassifier())
    outcome = recorder.record_turn(
        turn=slice_,
        existing=_summary(),
        key=RelationshipRecorderKey(
            candidates=(
                memory_candidate("The user loves rainy days."),
                memory_candidate("The user keeps a rain journal."),
            )
        ),
    )
    assert outcome.proposals == ()
    assert {item.reason for item in outcome.refusals} == {
        "COMMAND_TURN_CLASSIFICATION_UNAVAILABLE"
    }
    # One refusal per candidate: nothing was judged and nothing was proposed,
    # so no proposal can hide behind the retryable refusal.
    assert len(outcome.refusals) == 2


def test_the_recorder_is_deterministic_and_writes_nothing(
    store: SqliteConversationStore, recorder: RelationshipRecorder
) -> None:
    """Purity: the same (slice, summary, key) always yields the same outcome —
    the proposals are a function of the allow-listed inputs and nothing
    else."""

    conversation = open_conversation_for(store, "conv-rel-7", PERSONA_A)
    turn_id = speak(store, conversation, "cm-1", "My sister lives in Kyoto.")
    deliver_reply(store, turn_id, conversation, "Kyoto is beautiful.")
    slice_ = turn_slice(store, turn_id)
    summary = _summary()
    asserted = (
        memory_candidate("The user's sister lives in Kyoto."),
        memory_candidate(
            "They talked about Kyoto.",
            memory_type=RelationshipMemoryType.SHARED_EVENT,
        ),
    )

    first = record_turn(recorder, slice_, summary, *asserted)
    second = record_turn(recorder, slice_, summary, *asserted)
    assert first == second
    assert len(first.proposals) == 2


def test_the_command_turn_predicate_is_the_shipped_one() -> None:
    """The P4-G1 predicate moved into the module (P4-1 ①): the same behaviour
    is pinned now against the shipped rule, including the boundary that the
    red line names exactly three assertion types."""

    for memory_type in (
        RelationshipMemoryType.USER_STATED_FACT.value,
        RelationshipMemoryType.CONVERSATION_PREFERENCE.value,
        RelationshipMemoryType.SHARED_EVENT.value,
    ):
        refusal = command_turn_memory_refusal(
            is_command_turn=True, memory_type=memory_type
        )
        assert refusal is not None
        assert "command turn" in refusal
    assert (
        command_turn_memory_refusal(
            is_command_turn=True,
            memory_type=RelationshipMemoryType.OPEN_THREAD.value,
        )
        is None
    )
    assert (
        command_turn_memory_refusal(
            is_command_turn=False,
            memory_type=RelationshipMemoryType.USER_STATED_FACT.value,
        )
        is None
    )


def test_the_p4_g1_seam_satisfies_the_recorder_protocol(
    store: SqliteConversationStore,
) -> None:
    """The durable classifier really is the protocol the Recorder requires —
    structural conformance, no adapter in between."""

    assert isinstance(store, CommandTurnClassifier)


def test_a_citation_of_the_turns_own_id_resolves(
    store: SqliteConversationStore, recorder: RelationshipRecorder
) -> None:
    """The slice's own durable ids are the whole citation namespace: the
    coordination turn id and the user turn id both resolve, anything else
    does not (rule 5)."""

    conversation = open_conversation_for(store, "conv-rel-9", PERSONA_A)
    turn_id = speak(store, conversation, "cm-1", "I cycle to work.")
    slice_ = turn_slice(store, turn_id)

    outcome = record_turn(
        recorder,
        slice_,
        _summary(),
        memory_candidate(
            "The user cycles to work.", cited=(str(slice_.turn_id),)
        ),
    )
    assert outcome.refusals == ()
    assert outcome.proposals[0].source_turn_id == slice_.turn_id


def test_the_recorder_refuses_nothing_when_no_candidate_is_declared(
    store: SqliteConversationStore, recorder: RelationshipRecorder
) -> None:
    conversation = open_conversation_for(store, "conv-rel-8", PERSONA_A)
    turn_id = speak(store, conversation, "cm-1", "Just chatting.")
    slice_ = turn_slice(store, turn_id)

    outcome = record_turn(recorder, slice_, _summary())
    assert outcome == RelationshipRecorderOutcome((), ())
