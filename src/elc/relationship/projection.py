"""CP4 projection executors — the execution faces of §5 and §5.3 (P4-2/P4-3).

docs/DOMAIN_MODEL.md §5 owns the relationship write flow (Recorder proposal →
validate / dedupe → canonical Relationship Memory) and docs/DATA_MODEL.md
§5.3 owns the episode row; docs/RUNTIME_ARCHITECTURE.md §19 runs both *after*
the canonical turn ("默认在 canonical turn 后运行") and §CP4 lists them as the
Phase 4 projections. This module is the glue: the per-type
:class:`elc.runtime.projections.ProjectionExecutor` implementations the CP4
runtime dispatches to — :class:`RelationshipProjectionExecutor` (P4-2) and
:class:`EpisodeProjectionExecutor` (P4-3), one per entry of
``elc.runtime.projections.SUPPORTED_PROJECTION_TYPES``.

Consumption surface (P4-G1, unchanged): the executor feeds the Recorder the
same two allow-listed inputs it always took — the CanonicalTurnSlice and the
same-persona relationship summary — and nothing else. It deliberately does
**not** classify command turns: the durable classifier inside the Recorder
is the single authority for that red line, and a second heuristic here would
be exactly the drift the P4-G1 pin forbids.

Scope: the Persona×User pair travels on the constructor (``user_id``) and on
the conversation (``persona_id``), and every proposal the Recorder assembles
    is bound to that pair. The assembly check in :meth:`project` refuses a
summary whose scope is *not* the pair this executor is responsible for —
with zero writes — so a mis-assembled summary can never become another
persona's memory (DEC-OPI-5ba74efc.115 待裁 B 附条件; DOMAIN_MODEL §17;
BF-05 §29).

Failure semantics: every face returns a ``Result``; nothing raises. The
runtime maps an ``Err`` by its code — VALIDATION_FAILED /
AUTHORITY_VIOLATION / CONFLICT reject the job deterministically, anything
else leaves it retryable (elc.runtime.projections owns that mapping). Two
producers of a retryable ``Err`` live here: a candidate provider whose read
is down, and the Recorder's fail-closed classifier refusal — the latter is a
failed *read* of durable state, never a memory verdict, so it must not be
committed as an empty projection (see
:meth:`RelationshipProjectionExecutor.project`).

Package constraints hold here as everywhere in ``elc.relationship``: no
import of ``elc.learning`` / ``elc.teaching`` / ``elc.persona``, and no
sqlite3 / SQL (both are AST-pinned).
"""

from __future__ import annotations

from typing import Protocol, TypeVar, runtime_checkable

from elc.conversation.types import CanonicalTurnSlice, ConversationStatus
from elc.platform.types import (
    ConversationId,
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    PersonaId,
    Result,
    UserId,
)
from elc.relationship.controller import RelationshipController
from elc.relationship.episode import (
    EPISODE_ABSENT_BASE_VERSION,
    EPISODE_WINDOW_MAX_TURNS,
    EpisodeConversationSource,
    EpisodeRecord,
    rebuild_episode,
)
from elc.relationship.episode_store import SqliteEpisodeStore
from elc.relationship.recorder import (
    REFUSAL_CLASSIFIER_UNAVAILABLE,
    RelationshipMemoryCandidate,
    RelationshipRecorder,
    RelationshipRecorderKey,
)
from elc.runtime.projections import (
    PROJECTION_TYPE_EPISODE,
    PROJECTION_TYPE_RELATIONSHIP,
    ProjectionJobView,
    ProjectionTurnSource,
    base_version_for,
)
from elc.runtime.types import TurnRecordData

__all__ = [
    "EpisodeProjectionExecutor",
    "RelationshipCandidateProvider",
    "RelationshipProjectionExecutor",
]


@runtime_checkable
class RelationshipCandidateProvider(Protocol):
    """The model-candidate source of one turn (the MODEL_PROPOSAL face).

    This is the BF-05 trust class "LLM relationship proposal": what was
    asserted about the turn. The provider is a *source*, never an authority —
    every candidate it hands back still walks the Recorder's red lines and
    the Domain Controller's validate / gate faces, so a provider cannot
    smuggle a memory past either. ``None`` at construction means "this
    assembly has no provider": the executor passes an empty key, the Recorder
    proposes nothing, and the projection commits having done exactly that
    (the honest Local V1 shape when no model is wired).
    """

    def candidates_for(
        self, turn: CanonicalTurnSlice
    ) -> Result[tuple[RelationshipMemoryCandidate, ...]]:
        ...


class RelationshipProjectionExecutor:
    """The ``RELATIONSHIP`` projection: one canonical turn in, memories out.

    A thin, honest policy shell: it resolves the turn's Persona×User scope,
    assembles the Recorder's two allow-listed inputs, runs the recorder, and
    hands every proposal to the Domain Controller — which owns
    validate/dedupe and the BF-05 gate. It writes nothing itself
    (DOMAIN_MODEL §18 "Proposal-only Components": the Recorder proposes, the
    Controller decides).
    """

    #: The §22.1 type word this executor serves (elc.runtime.projections'
    #: dispatch key — the class attribute satisfies the Protocol's property).
    projection_type = PROJECTION_TYPE_RELATIONSHIP

    def __init__(
        self,
        *,
        recorder: RelationshipRecorder,
        controller: RelationshipController,
        conversation: ProjectionTurnSource,
        user_id: UserId,
        candidates: RelationshipCandidateProvider | None = None,
    ) -> None:
        self._recorder = recorder
        self._controller = controller
        self._conversation = conversation
        self._user_id = user_id
        self._candidates = candidates

    # -- ProjectionExecutor ------------------------------------------------

    def base_version(self, turn: TurnRecordData) -> Result[str]:
        """The current base: the same-persona summary's digest.

        Recomputed on every run (never read back from a job row), so a retry
        after the base moved writes the *current* base into the durable
        ``base_domain_version`` column (DATA_MODEL §22.1 version-aware
        revalidation). A conversation without a persona has no relationship
        scope to project into, so it refuses with VALIDATION_FAILED — the
        deterministic code the runtime rejects the job with.
        """

        persona = self._persona_for(ConversationId(turn.conversation_id))
        if isinstance(persona, Err):
            return persona
        summary = self._controller.get_existing_summary(
            persona.value, self._user_id
        )
        if isinstance(summary, Err):
            return summary
        return Ok(base_version_for(summary.value))

    def project(self, view: ProjectionJobView) -> Result[str]:
        """Run one claimed RELATIONSHIP job; returns a count summary.

        The order is fixed and each step is a refusal, never a partial write:

        1. read the turn's canonical slice (the job's source);
        2. resolve the conversation's persona — without one there is no
           Persona×User scope, so there is nothing this projection could
           legally write;
        3. read the same-persona summary and check that its scope *is* this
           executor's pair (the assembly consistency check);
        4. ask the candidate provider what was asserted about the turn;
        5. record (the P4-G1-gated Recorder — it applies the command-turn red
           line and the refusal order) and propose every surviving proposal
           through the Domain Controller.

        Refusals are counted, never fatal: a proposal the Controller refuses
        is a durable verdict about that memory, not a failure of the
        projection (DOMAIN_MODEL §5: a projection failure never rolls the
        conversation back), and a recorder refusal is likewise part of the
        outcome the Recorder reports.

        One refusal is *not* counted: the classifier-unavailable one. The
        Recorder fails closed there (an unclassifiable turn produces no
        proposal at all — P4-1), but that is a failed **read** of the durable
        classifier, not a verdict about a memory. Reporting it as an empty
        success would commit the job under its deterministic id while a later,
        working assembly replays that row as finished work forever — the turn
        would be projected by nobody, permanently. It is returned as a
        dependency-grade ``Err``, which the runtime leaves retryable
        (DATA_MODEL §22.1); the retry recomputes the same slice hash and lands
        whatever the read could not see.
        """

        slice_result = self._conversation.get_canonical_turn_slice(
            view.source_turn_id
        )
        if isinstance(slice_result, Err):
            return slice_result
        slice_ = slice_result.value
        if slice_ is None:
            return _refusal(
                f"canonical turn slice not found: {view.source_turn_id}"
            )
        persona = self._persona_for(slice_.conversation_id)
        if isinstance(persona, Err):
            return persona
        summary = self._controller.get_existing_summary(
            persona.value, self._user_id
        )
        if isinstance(summary, Err):
            return summary
        existing = summary.value
        if (
            existing.persona_id != persona.value
            or existing.user_id != self._user_id
        ):
            # DEC-…115 待裁 B 附条件 (assembly consistency check): a summary
            # that does not describe *this* pair must never feed the
            # Recorder — the row it would produce is bound to the summary's
            # scope, so a mis-assembled summary would write another persona's
            # memory. Refused with zero writes.
            return _refusal(
                "relationship summary scope mismatch: the summary describes"
                f" ({existing.persona_id}, {existing.user_id}) but this"
                f" projection is scoped to ({persona.value}, {self._user_id})"
                " (DOMAIN_MODEL §17; BF-05 §29)"
            )

        candidates: tuple[RelationshipMemoryCandidate, ...] = ()
        if self._candidates is not None:
            provided = self._candidates.candidates_for(slice_)
            if isinstance(provided, Err):
                return provided
            candidates = provided.value

        outcome = self._recorder.record_turn(
            turn=slice_,
            existing=existing,
            key=RelationshipRecorderKey(candidates=candidates),
        )
        unreadable = [
            refusal
            for refusal in outcome.refusals
            if refusal.reason == REFUSAL_CLASSIFIER_UNAVAILABLE
        ]
        if unreadable:
            # The Recorder failed closed (zero proposals); see the docstring
            # above for why that must not be committed as an empty success.
            # DEPENDENCY_UNAVAILABLE is deliberately *not* one of the
            # deterministic codes, so the runtime keeps the job retryable.
            # The premise this branch reads — "the word implies proposals
            # == ()", i.e. the retry can never hide a proposal — is the
            # recorder's own early-return arm (elc.relationship.recorder
            # ``record_turn``), pinned beside it by
            # tests/phase4/test_p4_1_recorder.py
            # ::test_the_classifier_refusal_implies_zero_proposals.
            return Err(
                DomainError(
                    code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                    message=(
                        "the command-turn classification could not be read"
                        f" ({unreadable[0].detail}); the Recorder failed"
                        " closed (no proposal at all), so this job stays"
                        " retryable instead of committing an empty projection"
                    ),
                )
            )
        committed = 0
        refused = 0
        for proposal in outcome.proposals:
            written = self._controller.propose_memory(proposal)
            if isinstance(written, Ok):
                committed += 1
            else:
                refused += 1
        return Ok(
            f"proposals={len(outcome.proposals)} committed={committed}"
            f" controller_refusals={refused}"
            f" recorder_refusals={len(outcome.refusals)}"
        )

    # -- internals ---------------------------------------------------------

    def _persona_for(self, conversation_id: ConversationId) -> Result[PersonaId]:
        conversation = self._conversation.get_conversation(conversation_id)
        if isinstance(conversation, Err):
            return conversation
        record = conversation.value
        if record is None:
            return _refusal(
                f"conversation not found: {conversation_id}"
            )
        if record.persona_id is None:
            return _refusal(
                f"conversation {conversation_id} has no persona; a"
                " relationship projection needs the Persona×User pair it"
                " would write for (DOMAIN_MODEL §5)"
            )
        return Ok(record.persona_id)


class EpisodeProjectionExecutor:
    """The ``EPISODE`` projection: one canonical turn in, a rebuilt row out.

    docs/DATA_MODEL.md §5.3 is the row, elc.relationship.episode is what it
    means, and this class is the CP4 execution face between them — the
    RelationshipProjectionExecutor precedent, one type over:

    1. read the turn's canonical slice (the job's source — the same source
       the job's ``source_turn_slice_hash`` was computed from);
    2. resolve the conversation's persona — the episode's ``open_threads``
       column is the *pair's* ACTIVE OPEN_THREAD memories, so without a
       persona this projection has a Persona×User leg it cannot honestly
       fill (a fabricated empty scope is exactly the assembly drift the P4-2
       review refused). No persona = the deterministic refusal
       ``VALIDATION_FAILED``, the code the runtime rejects the job with, so
       both Phase-4 projections share one eligibility rule;
    3. read the conversation window the episode summarizes;
    4. read the pair's existing relationship summary — the one allow-listed
       input (DOMAIN_MODEL §17: the pair is bound into that read);
    5. :func:`elc.relationship.episode.rebuild_episode` and
       :meth:`SqliteEpisodeStore.upsert_episode`.

    Idempotence is the store's: rebuilding the same truth yields the same
    content version, and the store turns that into a zero-write replay
    (DATA_MODEL §26 — an episode is a rebuildable projection).

    Failure semantics match the relationship executor: every face returns a
    ``Result``, nothing raises, and the runtime maps the code
    (VALIDATION_FAILED / AUTHORITY_VIOLATION / CONFLICT reject the job;
    anything else leaves it retryable). A conversation whose status changed,
    a window that lost its slices, a store write that conflicts — all of
    them are reported, none of them touches the transcript (RA §19).
    """

    #: The §22.1 type word this executor serves.
    projection_type = PROJECTION_TYPE_EPISODE

    def __init__(
        self,
        *,
        store: SqliteEpisodeStore,
        controller: RelationshipController,
        conversation: EpisodeConversationSource,
        user_id: UserId,
        window_max_turns: int = EPISODE_WINDOW_MAX_TURNS,
    ) -> None:
        self._store = store
        self._controller = controller
        self._conversation = conversation
        self._user_id = user_id
        self._window_max_turns = window_max_turns

    # -- ProjectionExecutor ------------------------------------------------

    def base_version(self, turn: TurnRecordData) -> Result[str]:
        """The current base: the conversation's episode version, or the
        sentinel when it has none.

        Recomputed from the durable row on every run (never read back from
        the job), so a retry after the episode moved records the *current*
        base (DATA_MODEL §22.1 version-aware revalidation). The absent case
        is not an error: the first projection of a conversation legitimately
        starts from nothing, and the sentinel says so instead of pretending
        to be a digest (elc.relationship.episode
        ``EPISODE_ABSENT_BASE_VERSION``).
        """

        current = self._store.get_episode(ConversationId(turn.conversation_id))
        if isinstance(current, Err):
            return current
        if current.value is None:
            return Ok(EPISODE_ABSENT_BASE_VERSION)
        return Ok(current.value.version)

    def project(self, view: ProjectionJobView) -> Result[str]:
        """Run one claimed EPISODE job; returns the landed version text."""

        slice_result = self._conversation.get_canonical_turn_slice(
            view.source_turn_id
        )
        if isinstance(slice_result, Err):
            return slice_result
        slice_ = slice_result.value
        if slice_ is None:
            return _refusal(
                f"canonical turn slice not found: {view.source_turn_id}"
            )
        conversation_id = slice_.conversation_id
        persona = self._persona_for(conversation_id)
        if isinstance(persona, Err):
            return persona
        summary = self._controller.get_existing_summary(
            persona.value, self._user_id
        )
        if isinstance(summary, Err):
            return summary
        existing = summary.value
        if (
            existing.persona_id != persona.value
            or existing.user_id != self._user_id
        ):
            # The same assembly consistency check the relationship executor
            # runs (DEC-…115 待裁 B 附条件): a summary describing another
            # pair must never become this conversation's open threads.
            return _refusal(
                "relationship summary scope mismatch: the summary describes"
                f" ({existing.persona_id}, {existing.user_id}) but this"
                f" projection is scoped to ({persona.value}, {self._user_id})"
                " (DOMAIN_MODEL §17; BF-05 §29)"
            )
        status_result = self._conversation.get_conversation(conversation_id)
        if isinstance(status_result, Err):
            return status_result
        conversation = status_result.value
        if conversation is None:
            return _refusal(f"conversation not found: {conversation_id}")
        window_result = self._conversation.get_conversation_window(
            conversation_id, self._window_max_turns
        )
        if isinstance(window_result, Err):
            return window_result
        rebuilt = rebuild_episode(
            conversation_id=conversation_id,
            slices=window_result.value.slices,
            relationship_summary=existing,
            conversation_status=conversation.status,
        )
        if isinstance(rebuilt, Err):
            return rebuilt
        record: EpisodeRecord = rebuilt.value
        written = self._store.upsert_episode(record)
        if isinstance(written, Err):
            return written
        return Ok(
            f"episode={record.episode_id} version={record.version}"
            f" turns={record.source_turn_sequence_start}-"
            f"{record.source_turn_sequence_end}"
            f" open_threads={len(record.open_threads)}"
            f" recent_events={len(record.recent_events)}"
            f" status={ConversationStatus(record.status).value}"
        )

    # -- internals ---------------------------------------------------------

    def _persona_for(self, conversation_id: ConversationId) -> Result[PersonaId]:
        conversation = self._conversation.get_conversation(conversation_id)
        if isinstance(conversation, Err):
            return conversation
        record = conversation.value
        if record is None:
            return _refusal(f"conversation not found: {conversation_id}")
        if record.persona_id is None:
            return _refusal(
                f"conversation {conversation_id} has no persona; an episode's"
                " open threads are the Persona×User pair's memories, so the"
                " projection needs the pair it would read (DOMAIN_MODEL §5)"
            )
        return Ok(record.persona_id)


_E = TypeVar("_E")


def _refusal(message: str) -> Err[_E]:
    return Err(
        DomainError(code=DomainErrorCode.VALIDATION_FAILED, message=message)
    )
