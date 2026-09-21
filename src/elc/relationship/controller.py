"""Relationship Domain Controller — Persona×User memory truth (P4-1).

Phase 4 P4-1 (TASK-OPI-5ba74efc-….100 ②③④⑤): this controller graduates
from the Phase 0 empty skeleton into the real Relationship authority face
(the P3-0/P3-1A LearningController / TeachingController graduation
precedent). docs/DOMAIN_MODEL.md §18: the Domain Controller decides VALIDATE
/ COMMIT / REJECT / ABSTAIN; §5's write flow is

    Relationship Recorder proposal
    → Relationship Domain validate/dedupe
    → canonical Relationship Memory

so this controller is a delegating authority face over the domain's own
durable store, and the policy halves live in pure modules:

- :mod:`elc.relationship.validation` — what "well-formed and traceable"
  means and what "already remembered" means (validate + dedupe rule),
- :mod:`elc.relationship.sensitivity` — the BF-05 sensitive-memory gate,
- :mod:`elc.relationship.store` — the durable rows, the epoch fence, and
  every SQL statement.

The write face runs the same gate the Recorder runs: a hand-assembled
proposal cannot bypass BF-05 by skipping the proposal component (defence in
depth, both halves pinned).

Failure semantics (DOMAIN_MODEL §5 "Relationship projection failure 不回滚
conversation turn"): every face returns a ``Result``; nothing raises into a
caller except a stale-epoch store (a programming error, the repo-wide
fence convention). Wiring this face into the turn pipeline / a post-turn
queue belongs to P4-2 — this slice does not auto-attach it anywhere.

Memory ids: deterministic and replay-safe (elc.relationship.validation
``memory_id_for``), so a crash-retry of the same proposal re-derives the same
id and the store turns it into an idempotent replay instead of a duplicate.

``validator_version``: P4-1's write path is the TRUSTED_AUTHORITY
"domain-validated canonical write" of DOMAIN_MODEL §18.1 — not a
model-assisted validator — so the durable column stays NULL by design
(ratified in the P4-0 review disposition, F6). An assembly that *does* run a
model-assisted validator passes its version to the constructor and it is
recorded.

Frozen Phase 0 protocol shapes: ``supersede_memory(memory_id, replacement)``
carries no recorder identity and no BF-05 sensitivity/authorization pair, so
it cannot assemble an honest durable row (``recorder_version`` is NOT NULL
and an empty version is refused) — it raises with a pointer to the real
entry point, the P3-1A/1B precedent. ``get_memory(memory_id)`` has no
Persona×User leg either, and an id-only read would make cross-persona reads
expressible (§17 "Relationship 不跨 Persona 泄漏"; BF-05 §29); the real read
is :meth:`get_scoped_memory`, which is scoped by the pair.
"""

from __future__ import annotations

from elc.platform.types import (
    DomainError,
    DomainErrorCode,
    Err,
    PersonaId,
    RelationshipMemoryId,
    Result,
    UserId,
)
from elc.relationship.sensitivity import decide_persistence
from elc.relationship.store import SqliteRelationshipStore
from elc.relationship.types import (
    MemoryStatus,
    RelationshipMemoryProposal,
    RelationshipMemoryRecord,
    RelationshipView,
    SamePersonaExistingRelationshipSummary,
)
from elc.relationship.validation import memory_id_for, validate_proposal

__all__ = ["RelationshipController"]


class RelationshipController:
    """Owns Persona×User memory truth over SqliteRelationshipStore."""

    def __init__(
        self,
        store: SqliteRelationshipStore,
        *,
        validator_version: str | None = None,
    ) -> None:
        self._store = store
        #: Recorded as the durable ``validator_version``. None = the
        #: TRUSTED_AUTHORITY domain-validated write (the P4-1 path); a
        #: model-assisted validator assembly names itself here.
        self._validator_version = validator_version

    # -- the write face (§5) ------------------------------------------------

    def propose_memory(
        self, proposal: RelationshipMemoryProposal
    ) -> Result[RelationshipMemoryId]:
        """Validate → gate → commit one proposal (§5; §18 VALIDATE/COMMIT).

        Returns the durable memory id. A duplicate of an ACTIVE memory
        dedupes to that memory's id (nothing written); a declared supersede
        appends the replacement and flips the old row to SUPERSEDED in the
        same short transaction. Refusals come back as ``Err`` — validation,
        the BF-05 gate, and the store's conflict/authority faces.

        Error codes: a refusal is VALIDATION_FAILED (the write is not legal in
        this form — including the gate's DENY), a cross-persona supersede
        target is AUTHORITY_VIOLATION, and an id clash with a different
        payload is CONFLICT.
        """

        violation = validate_proposal(proposal)
        if violation is not None:
            return Err(violation)
        decision = decide_persistence(
            sensitivity_class=proposal.sensitivity_class,
            persistence_authorization=proposal.persistence_authorization,
            provenance=proposal.provenance,
        )
        if not decision.allowed:
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=f"{decision.reason}: {decision.detail}",
                )
            )
        record = RelationshipMemoryRecord(
            relationship_memory_id=memory_id_for(proposal),
            persona_id=proposal.persona_id,
            user_id=proposal.user_id,
            memory_type=proposal.memory_type,
            provenance=proposal.provenance,
            canonical_content=proposal.content,
            source_turn_id=proposal.source_turn_id,
            status=MemoryStatus.ACTIVE,
            source_turn_ids=proposal.source_turn_ids,
            provenance_refs=proposal.provenance_refs,
            confidence=proposal.confidence,
            supersedes_memory_id=proposal.supersedes_memory_id,
            recorder_version=proposal.recorder_version,
            validator_version=self._validator_version,
            sensitivity_class=proposal.sensitivity_class,
            persistence_authorization=proposal.persistence_authorization,
        )
        return self._store.commit_memory(record)

    def supersede_memory(
        self, memory_id: RelationshipMemoryId, replacement: str
    ) -> Result[RelationshipMemoryId]:
        raise NotImplementedError(
            "the frozen Phase 0 shape carries no recorder identity and no"
            " BF-05 sensitivity/authorization pair, so it cannot fill the"
            " NOT NULL recorder_version honestly; supersede through"
            " propose_memory(RelationshipMemoryProposal(...,"
            " supersedes_memory_id=memory_id)) (P4-1)"
        )

    # -- reads (§4 view, the Recorder's summary, the scoped read) -----------

    def get_relationship_view(
        self, persona_id: PersonaId, user_id: UserId
    ) -> Result[RelationshipView]:
        """The ACTIVE memories of one Persona×User pair (docs/DOMAIN_MODEL
        §4 RelationshipView)."""

        return self._store.get_relationship_view(persona_id, user_id)

    def get_existing_summary(
        self, persona_id: PersonaId, user_id: UserId
    ) -> Result[SamePersonaExistingRelationshipSummary]:
        """The Recorder's second allow-listed input (BF-05
        ``SamePersonaExistingRelationshipSummary``) — one pair, ACTIVE rows."""

        return self._store.get_existing_summary(persona_id, user_id)

    def get_scoped_memory(
        self,
        persona_id: PersonaId,
        user_id: UserId,
        memory_id: RelationshipMemoryId,
    ) -> Result[RelationshipMemoryRecord | None]:
        """One memory, only within its own Persona×User pair (§17; §29)."""

        return self._store.get_scoped_memory(persona_id, user_id, memory_id)

    def get_memory(
        self, memory_id: RelationshipMemoryId
    ) -> Result[RelationshipMemoryRecord | None]:
        raise NotImplementedError(
            "the frozen Phase 0 shape has no Persona×User leg, and an id-only"
            " read would make cross-persona reads expressible (DOMAIN_MODEL"
            " §17; BF-05 §29); use get_scoped_memory(persona_id, user_id,"
            " memory_id) (P4-1)"
        )
