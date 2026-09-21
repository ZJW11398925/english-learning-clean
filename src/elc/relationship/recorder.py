"""Relationship Recorder — the §5 write flow's first leg (P4-1).

docs/DOMAIN_MODEL.md §5:

    Relationship Recorder proposal
    → Relationship Domain validate/dedupe
    → canonical Relationship Memory

and §18 "Proposal-only Components": the Recorder proposes, the Domain
Controller decides VALIDATE / COMMIT / REJECT / ABSTAIN. This module is the
proposal face only — it writes nothing, and it holds no SQL.

Consumption surface (P4-G1; BF-05
``security_privacy_policy_v1.json`` → ``provider_actions.
RELATIONSHIP_PROPOSAL``, word for word: allow = ``CanonicalTurnSlice`` +
``SamePersonaExistingRelationshipSummary``; deny = ``LearnerState`` /
``LearningEvidence`` / ``TeachingTrace`` / ``OtherPersonaRelationship`` /
``APISecret``). The Recorder's *state* inputs are exactly those two, and its
third parameter is not state at all: ``key`` is the MODEL_PROPOSAL bundle
(BF-05 ``trust_classes``: "LLM relationship proposal") — what was asserted
about the turn, declared as data, exactly as the attempt evaluator takes a
declared ``AttemptAnswerKey`` instead of a model. There is no provider and
no model call in this slice; a caller that has no assertions passes an empty
key and gets an empty outcome.

Two surfaces are deliberately *not* taken from the Recorder's caller:
- the Persona×User scope travels on the summary (a CanonicalTurnSlice knows
  its conversation but not its persona; DOMAIN_MODEL §5's unit is
  Persona × User). Assembling the summary for the turn's conversation is the
  caller's job (P4-2's turn pipeline); the Recorder binds every proposal to
  the summary's scope and can reach no other scope.
- the command-turn classification is a durable read
  (``is_command_payload_turn``), never a heuristic over the text
  (TASK-…5ba74efc.100 ①; the P4-G1 pin). The Recorder fails closed when the
  classification cannot be answered: an unclassifiable turn produces no
  proposal at all.

Refusal order per candidate (fixed, documented, tested):

1. **BF-05 sensitivity gate** — a candidate the gate denies (inferred
   high-sensitivity attribute, or high sensitivity without explicit
   persistence permission) never becomes a proposal
   (elc.relationship.sensitivity is the single rule set; the write face
   applies the same gate again, so a hand-assembled proposal cannot bypass
   it);
2. **command turns say nothing** — a TEACHING_REQUEST / TEACHING_RESPONSE
   command turn is a typed coordination payload with an empty utterance, so
   it is never read as USER_STATED_FACT / CONVERSATION_PREFERENCE /
   SHARED_EVENT (VAL-…72 ⑤; DOMAIN_MODEL §18.1 UNTRUSTED_CONTENT);
3. **USER_STATED_FACT needs a real user turn** — the claim "the user said
   this" cannot rest on silence (BF-05 §7); without a user utterance the
   candidate is refused rather than re-typed by the Recorder;
4. **delivered assistant output only** — a memory that asserts something
   about the *pair* (an episode, a running joke) or about the persona's own
   stance (an impression) needs the turn's assistant side to be canonical
   and delivered; undelivered provider output never enters Relationship
   (IP §4 Acceptance①);
5. **refs must resolve inside the slice** — every cited durable id must be
   one of the slice's own canonical ids; an id the transcript never
   canonicalized (an undelivered provider draft, or anything from outside
   the turn) is refused, and so is a memory that would cite it;
6. **supersede targets must be in the same-persona summary** — a pointer
   that is not there is refused without disclosing whether it exists for
   another persona (BF-05 §29; DOMAIN_MODEL §17).

A refusal is returned, never raised: the Recorder is a projection-side
component and its failure must not travel into the conversation turn
(DOMAIN_MODEL §5 "Relationship projection failure 不回滚 conversation
turn").
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from elc.conversation import CANONICAL_DELIVERY_STATES, CanonicalTurnSlice
from elc.platform.types import (
    Err,
    RelationshipMemoryId,
    Result,
    TurnId,
)
from elc.relationship.sensitivity import decide_persistence
from elc.relationship.types import (
    MemoryProvenance,
    MemorySensitivityClass,
    PersistenceAuthorization,
    RelationshipMemoryProposal,
    RelationshipMemoryType,
    SamePersonaExistingRelationshipSummary,
)

__all__ = [
    "ASSISTANT_GROUNDED_MEMORY_TYPES",
    "COMMAND_TURN_ASSERTION_MEMORY_TYPES",
    "REFUSAL_ASSISTANT_OUTPUT_NOT_CANONICAL",
    "REFUSAL_CLASSIFIER_UNAVAILABLE",
    "REFUSAL_COMMAND_TURN",
    "REFUSAL_SUPERSEDE_TARGET_OUT_OF_SCOPE",
    "REFUSAL_UNRESOLVED_REF",
    "REFUSAL_USER_STATED_WITHOUT_USER_TURN",
    "RELATIONSHIP_RECORDER_ID",
    "RELATIONSHIP_RECORDER_VERSION",
    "CommandTurnClassifier",
    "RelationshipMemoryCandidate",
    "RelationshipMemoryRefusal",
    "RelationshipRecorder",
    "RelationshipRecorderKey",
    "RelationshipRecorderOutcome",
    "command_turn_memory_refusal",
]

#: The Recorder's identity (docs/DATA_MODEL.md §1.4 "version every derived
#: model"): written into every durable row's ``recorder_version``.
RELATIONSHIP_RECORDER_ID = "relationship-recorder-v0"
RELATIONSHIP_RECORDER_VERSION = "v0"

#: The memory types a command turn must never be read as: each asserts
#: something about what the *user* said or prefers (VAL-…72 ⑤ names
#: USER_STATED_FACT / conversation preference / shared event). A command
#: turn's utterance is empty by construction — it carries a typed payload —
#: so there is nothing to have said. The remaining five §5 types are not
#: assertions about the user's own words and are not part of this red line.
COMMAND_TURN_ASSERTION_MEMORY_TYPES = (
    RelationshipMemoryType.USER_STATED_FACT.value,
    RelationshipMemoryType.CONVERSATION_PREFERENCE.value,
    RelationshipMemoryType.SHARED_EVENT.value,
)

#: Memory types that rest on the assistant side of the turn: an episode
#: *between* the two (SHARED_EVENT / RELATIONSHIP_EVENT / RUNNING_JOKE) or
#: the persona's own stance (PERSONA_IMPRESSION). Without a canonical,
#: delivered assistant turn those memories would assert a shared thing that
#: never happened (IP §4 Acceptance①: 未 delivery assistant output 不进入
#: Relationship). The user-side types (USER_STATED_FACT / PROMISE /
#: OPEN_THREAD / CONVERSATION_PREFERENCE) rest on the user's own turn.
ASSISTANT_GROUNDED_MEMORY_TYPES = (
    RelationshipMemoryType.SHARED_EVENT.value,
    RelationshipMemoryType.RELATIONSHIP_EVENT.value,
    RelationshipMemoryType.RUNNING_JOKE.value,
    RelationshipMemoryType.PERSONA_IMPRESSION.value,
)

#: Refusal reasons: which rule refused the candidate. Every refusal carries
#: one of these words plus a detail sentence — a silently dropped candidate
#: is exactly what this face exists to make impossible.
REFUSAL_COMMAND_TURN = "COMMAND_TURN_SAYS_NOTHING"
REFUSAL_CLASSIFIER_UNAVAILABLE = "COMMAND_TURN_CLASSIFICATION_UNAVAILABLE"
REFUSAL_USER_STATED_WITHOUT_USER_TURN = (
    "USER_STATED_FACT_WITHOUT_REAL_USER_TURN"
)
REFUSAL_ASSISTANT_OUTPUT_NOT_CANONICAL = "ASSISTANT_OUTPUT_NOT_CANONICAL"
REFUSAL_UNRESOLVED_REF = "PROVENANCE_REF_NOT_IN_THE_SLICE"
REFUSAL_SUPERSEDE_TARGET_OUT_OF_SCOPE = "SUPERSEDE_TARGET_OUT_OF_SCOPE"


@runtime_checkable
class CommandTurnClassifier(Protocol):
    """The seam that answers "is this turn a typed command, not an utterance".

    ``SqliteConversationStore`` satisfies it structurally
    (``is_command_payload_turn``: empty utterance + a TEACHING_REQUEST /
    TEACHING_RESPONSE payload marker, both bound parameters). The Recorder
    must read this durable answer and never re-derive the classification
    from the text — that is the P4-G1 pin.
    """

    def is_command_payload_turn(self, turn_id: TurnId) -> Result[bool]:
        ...


@dataclass(frozen=True)
class RelationshipMemoryCandidate:
    """One declared assertion about a turn (the MODEL_PROPOSAL face).

    The recorder's v0 counterpart of the evaluator's answer key: the caller
    declares what was asserted (a provider would have produced it), and the
    pure policy below decides whether it may become a proposal.

    ``cited_message_ids`` are the durable ids the content was read from —
    the model's provenance claim, checked against the slice (rule 5).
    ``supersedes_memory_id`` is the declared update semantics: the candidate
    corrects that memory instead of adding a second one (§1.3 append-first).
    """

    memory_type: RelationshipMemoryType
    provenance: MemoryProvenance
    content: str
    sensitivity_class: MemorySensitivityClass = MemorySensitivityClass.PERSONAL
    persistence_authorization: PersistenceAuthorization = (
        PersistenceAuthorization.VALIDATED_DOMAIN_WRITE
    )
    confidence: float | None = None
    supersedes_memory_id: RelationshipMemoryId | None = None
    cited_message_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class RelationshipRecorderKey:
    """The per-turn assertion bundle the Recorder reads a turn for."""

    candidates: tuple[RelationshipMemoryCandidate, ...] = ()


@dataclass(frozen=True)
class RelationshipMemoryRefusal:
    """One candidate that never became a proposal, and why.

    ``candidate_index`` is the 1-based position in the key, so a caller can
    line refusals up with what it declared; ``reason`` is one of the
    REFUSAL_* words and ``detail`` names the rule and its authority.
    """

    candidate_index: int
    memory_type: str
    reason: str
    detail: str


@dataclass(frozen=True)
class RelationshipRecorderOutcome:
    """Everything one turn produced: proposals, and the refusals with them.

    The refusals are part of the outcome rather than an error channel: a
    refused candidate is a normal, traceable outcome of the red lines, not a
    failure of the turn (DOMAIN_MODEL §5: the projection never rolls the
    conversation back).
    """

    proposals: tuple[RelationshipMemoryProposal, ...]
    refusals: tuple[RelationshipMemoryRefusal, ...]


def command_turn_memory_refusal(
    *, is_command_turn: bool, memory_type: str
) -> str | None:
    """The command-turn red-line predicate.

    Returns the refusal message when a candidate memory would assert
    something about the user's own words or preferences on a turn that said
    nothing, and ``None`` when the candidate is legal for that turn. The
    Recorder consults it for every candidate; it is exported so the P4-G1
    gate can keep pinning the rule itself.
    """

    if not is_command_turn:
        return None
    if memory_type in COMMAND_TURN_ASSERTION_MEMORY_TYPES:
        return (
            f"a command turn never becomes a {memory_type}: the turn carries"
            " a typed payload and an empty utterance, so nothing was said"
            " (DOMAIN_MODEL §18.1 UNTRUSTED_CONTENT; BF-05"
            " RELATIONSHIP_PROPOSAL)"
        )
    return None


class RelationshipRecorder:
    """Turns one CanonicalTurnSlice into §5 proposals (pure; writes nothing)."""

    def __init__(self, command_turns: CommandTurnClassifier) -> None:
        #: Required, not defaulted: without the durable classifier the
        #: command-turn red line cannot be applied, and a Recorder that
        #: silently skipped it would be the violation this face prevents.
        self._command_turns = command_turns

    @property
    def version(self) -> str:
        return RELATIONSHIP_RECORDER_VERSION

    def record_turn(
        self,
        *,
        turn: CanonicalTurnSlice,
        existing: SamePersonaExistingRelationshipSummary,
        key: RelationshipRecorderKey,
    ) -> RelationshipRecorderOutcome:
        """Read one turn and propose what may be remembered from it.

        The two state inputs are the BF-05 allow list (module docstring);
        ``key`` is the declared MODEL_PROPOSAL bundle. Every candidate either
        becomes a :class:`RelationshipMemoryProposal` (bound to the
        summary's Persona×User scope and traceable to the slice's own ids)
        or comes back as a :class:`RelationshipMemoryRefusal` naming the rule
        that refused it.
        """

        proposals: list[RelationshipMemoryProposal] = []
        refusals: list[RelationshipMemoryRefusal] = []

        classification = self._command_turns.is_command_payload_turn(turn.turn_id)
        if isinstance(classification, Err):
            # Fail closed: an unclassifiable turn could be a command turn, and
            # a command turn must never be read as an utterance.
            for index, candidate in enumerate(key.candidates, start=1):
                refusals.append(
                    _refusal(
                        index,
                        candidate,
                        REFUSAL_CLASSIFIER_UNAVAILABLE,
                        "the command-turn classification could not be read"
                        f" ({classification.error.message}); a turn that cannot"
                        " be proven not to be a command produces no memory"
                        " (P4-G1 / BF-05 RELATIONSHIP_PROPOSAL)",
                    )
                )
            return RelationshipRecorderOutcome((), tuple(refusals))

        is_command_turn = classification.value
        assistant_turn = turn.assistant_turn
        delivered_assistant = (
            assistant_turn is not None
            and assistant_turn.delivery_state in CANONICAL_DELIVERY_STATES
        )
        user_turn_id = str(turn.user_turn.user_turn_id)
        assistant_turn_id: str | None = None
        if delivered_assistant and assistant_turn is not None:
            assistant_turn_id = str(assistant_turn.assistant_turn_id)
        user_utterance = (
            turn.user_turn.normalized_content or turn.user_turn.raw_content
        ).strip()
        for index, candidate in enumerate(key.candidates, start=1):
            refusal = self._refuse_candidate(
                candidate=candidate,
                is_command_turn=is_command_turn,
                user_utterance=user_utterance,
                delivered_assistant=delivered_assistant,
                turn_id=str(turn.turn_id),
                user_turn_id=user_turn_id,
                assistant_turn_id=assistant_turn_id,
                existing=existing,
            )
            if refusal is not None:
                refusals.append(_refusal(index, candidate, *refusal))
                continue
            proposals.append(
                _proposal(
                    candidate=candidate,
                    turn=turn,
                    existing=existing,
                    user_turn_id=user_turn_id,
                    assistant_turn_id=assistant_turn_id,
                )
            )
        return RelationshipRecorderOutcome(tuple(proposals), tuple(refusals))

    def _refuse_candidate(
        self,
        *,
        candidate: RelationshipMemoryCandidate,
        is_command_turn: bool,
        user_utterance: str,
        delivered_assistant: bool,
        turn_id: str,
        user_turn_id: str,
        assistant_turn_id: str | None,
        existing: SamePersonaExistingRelationshipSummary,
    ) -> tuple[str, str] | None:
        """Apply the fixed refusal order; ``None`` = the candidate may pass."""

        decision = decide_persistence(
            sensitivity_class=candidate.sensitivity_class,
            persistence_authorization=candidate.persistence_authorization,
            provenance=candidate.provenance,
        )
        if not decision.allowed:
            return decision.reason, decision.detail
        command_refusal = command_turn_memory_refusal(
            is_command_turn=is_command_turn,
            memory_type=candidate.memory_type.value,
        )
        if command_refusal is not None:
            return REFUSAL_COMMAND_TURN, command_refusal
        if (
            candidate.provenance is MemoryProvenance.USER_STATED_FACT
            and not user_utterance
        ):
            return (
                REFUSAL_USER_STATED_WITHOUT_USER_TURN,
                "a USER_STATED_FACT must rest on a real user turn, but this"
                f" turn ({user_turn_id}) carries no user utterance; BF-05 §7:"
                " 'USER_STATED_FACT 必须有真实 UserTurn provenance' — a"
                " persona-generated claim about what the user said is at most"
                " a PERSONA_IMPRESSION",
            )
        if (
            candidate.memory_type.value in ASSISTANT_GROUNDED_MEMORY_TYPES
            and not delivered_assistant
        ):
            return (
                REFUSAL_ASSISTANT_OUTPUT_NOT_CANONICAL,
                f"a {candidate.memory_type.value} asserts something shared"
                " with, or held by, the persona, but this turn has no"
                " canonical delivered assistant output; undelivered provider"
                " output never enters Relationship (IP §4 Acceptance①;"
                " DOMAIN_MODEL §3 key rule)",
            )
        allowed_refs = {turn_id, user_turn_id}
        if assistant_turn_id is not None:
            allowed_refs.add(assistant_turn_id)
        unresolved = [
            ref for ref in candidate.cited_message_ids if ref not in allowed_refs
        ]
        if unresolved:
            return (
                REFUSAL_UNRESOLVED_REF,
                f"cited id(s) {sorted(unresolved)} are not canonical ids of"
                f" this turn ({sorted(allowed_refs)}); undelivered provider"
                " output never enters Relationship (IP §4 Acceptance①) and a"
                " memory may only cite what the transcript really kept"
                " (BF-05 §17)",
            )
        if (
            candidate.supersedes_memory_id is not None
            and existing.find(candidate.supersedes_memory_id) is None
        ):
            return (
                REFUSAL_SUPERSEDE_TARGET_OUT_OF_SCOPE,
                f"the memory it would correct"
                f" ({candidate.supersedes_memory_id}) is not part of this"
                " persona's existing relationship summary; another persona's"
                " memory is never visible here (DOMAIN_MODEL §17; BF-05 §29),"
                " so the pointer is refused without saying whether it exists",
            )
        return None


def _refusal(
    index: int,
    candidate: RelationshipMemoryCandidate,
    reason: str,
    detail: str,
) -> RelationshipMemoryRefusal:
    return RelationshipMemoryRefusal(
        candidate_index=index,
        memory_type=candidate.memory_type.value,
        reason=reason,
        detail=detail,
    )


def _proposal(
    *,
    candidate: RelationshipMemoryCandidate,
    turn: CanonicalTurnSlice,
    existing: SamePersonaExistingRelationshipSummary,
    user_turn_id: str,
    assistant_turn_id: str | None,
) -> RelationshipMemoryProposal:
    """Assemble the proposal from the slice: §23 provenance refs come from
    the turn the Recorder read, never from the caller's claim.

    The ref set always carries the coordination turn id (the row's own FK)
    *and* the real UserTurn id — BF-05 §7's "USER_STATED_FACT 必须有真实
    UserTurn provenance" is a fact about the refs, and the user turn is the
    concrete thing the user actually said. The assistant side joins the refs
    when the memory rests on it (or cites it), and the candidate's own
    resolved citations follow, deduped in a fixed order.
    """

    refs = [str(turn.turn_id), user_turn_id]
    if assistant_turn_id is not None and (
        candidate.memory_type.value in ASSISTANT_GROUNDED_MEMORY_TYPES
        or assistant_turn_id in candidate.cited_message_ids
    ):
        refs.append(assistant_turn_id)
    refs.extend(ref for ref in candidate.cited_message_ids if ref not in refs)
    return RelationshipMemoryProposal(
        persona_id=existing.persona_id,
        user_id=existing.user_id,
        memory_type=candidate.memory_type,
        provenance=candidate.provenance,
        content=candidate.content,
        source_turn_id=turn.turn_id,
        source_turn_ids=(turn.turn_id,),
        provenance_refs=tuple(refs),
        confidence=candidate.confidence,
        supersedes_memory_id=candidate.supersedes_memory_id,
        recorder_version=RELATIONSHIP_RECORDER_VERSION,
        sensitivity_class=candidate.sensitivity_class,
        persistence_authorization=candidate.persistence_authorization,
    )
