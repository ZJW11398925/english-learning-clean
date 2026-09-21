"""Relationship Domain validate/dedupe — the §5 write flow's middle leg.

docs/DOMAIN_MODEL.md §5:

    Relationship Recorder proposal
    → Relationship Domain validate/dedupe
    → canonical Relationship Memory

This module is that second leg as pure policy: no storage, no clock, no
randomness. The durable executor is elc.relationship.store and the §18
decision (VALIDATE / COMMIT / REJECT / ABSTAIN) belongs to
elc.relationship.controller; this module only says what "the proposal is
well-formed and traceable" means and what "this memory is already
remembered" means.

Validation rule set (each item cites its authority; ``validate_proposal``
returns the first violation as a VALIDATION_FAILED DomainError):

1. **Vocabulary** — ``memory_type`` / ``provenance`` are the canonical words
   of DOMAIN_MODEL §5 (the enums are the typed form; re-checked here so a
   proposal assembled by hand cannot smuggle a raw string past the domain
   boundary into the durable CHECK).
2. **Non-empty content** — a memory that says nothing is not a memory.
3. **Recorder version filled** — DATA_MODEL §1.4 "version every derived
   model"; the durable column is NOT NULL, and an empty string is not a
   version (review F6: the value is written, never defaulted to '').
4. **Scope legs non-empty** — the §5 unit is Persona × User, and both legs
   are NOT NULL in the schema.
5. **Traceability** — BF-05 §7 "``USER_STATED_FACT`` 必须有真实 UserTurn
   provenance" and §17 "Provenance 是删除的前提": every memory names at
   least one durable ref, and a user-stated fact names the real user turn it
   was read from.
6. **Coherence** — a memory *typed* USER_STATED_FACT is the user's own
   statement, so its provenance is USER_STATED_FACT. This is the write-face
   half of BF-05 §7's "Persona 自己生成「你以前告诉过我你喜欢 X」不能因此
   创造 USER_STATED_FACT" — a persona impression must not be laundered into
   "the user said it" by typing the row differently.
7. **Confidence** — DATA_MODEL §23 ``confidence?``: None for a user
   statement, a score for a validated inference (DOMAIN_MODEL §5 "Important
   distinction"). PERSONA_IMPRESSION is left unconstrained (an impression is
   neither a statement nor a scored inference).
8. **Supersede pointer sanity** — a memory never supersedes itself.

Dedupe rule (pinned, deterministic, documented): *normalized exact*
matching. Two contents are the same memory when they are equal after
:func:`normalize_memory_content` (whitespace-collapsed, edge punctuation
stripped, casefolded) — the in-repo precedent is the attempt evaluator's
``normalize_answer``, which exists for exactly this comparison form. Byte
equality was rejected: a re-stated fact that differs only in case or
trailing whitespace is the same memory, and appending a second row for it
would make the dedupe rule an accident of the client's typing.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence

from elc.platform.types import (
    DomainError,
    DomainErrorCode,
    RelationshipMemoryId,
)
from elc.relationship.types import (
    MemoryProvenance,
    MemoryStatus,
    RelationshipMemoryProposal,
    RelationshipMemoryRecord,
    RelationshipMemoryType,
)

__all__ = [
    "CANONICAL_MEMORY_PROVENANCE",
    "CANONICAL_MEMORY_TYPES",
    "PERSISTENCE_AUTHORIZATIONS",
    "RELATIONSHIP_VALIDATOR_ID",
    "RELATIONSHIP_VALIDATOR_VERSION",
    "SENSITIVITY_CLASSES",
    "find_duplicate",
    "memory_id_for",
    "normalize_memory_content",
    "validate_proposal",
]

#: The validator's identity (docs/DATA_MODEL.md §1.4). P4-1's write face is
#: the TRUSTED_AUTHORITY domain-validated write of DOMAIN_MODEL §18.1, so the
#: durable ``validator_version`` stays NULL by design (review F6); this
#: version names the pure rule set for traces and for a later model-assisted
#: validator assembly.
RELATIONSHIP_VALIDATOR_ID = "relationship-validator-v0"
RELATIONSHIP_VALIDATOR_VERSION = "v0"

#: DOMAIN_MODEL §5 "Memory types", word for word (eight).
CANONICAL_MEMORY_TYPES = (
    "USER_STATED_FACT",
    "SHARED_EVENT",
    "PERSONA_IMPRESSION",
    "PROMISE",
    "OPEN_THREAD",
    "RUNNING_JOKE",
    "RELATIONSHIP_EVENT",
    "CONVERSATION_PREFERENCE",
)

#: DOMAIN_MODEL §5 "Important distinction", word for word (three).
CANONICAL_MEMORY_PROVENANCE = (
    "USER_STATED_FACT",
    "SYSTEM_INFERRED_FACT",
    "PERSONA_IMPRESSION",
)

#: BF-05 data_classes legal for a relationship memory, word for word (the
#: pair migration 0009's CHECK pins).
SENSITIVITY_CLASSES = ("PERSONAL", "HIGH_SENSITIVITY")

#: BF-05 trust_classes / sensitive_memory_policy authorizations, word for
#: word (migration 0009's CHECK order).
PERSISTENCE_AUTHORIZATIONS = (
    "USER_EXPLICIT_CONSENT",
    "VALIDATED_DOMAIN_WRITE",
)

_WHITESPACE = re.compile(r"\s+")
_EDGE_PUNCTUATION = re.compile(r"^[^\w]+|[^\w]+$")


def normalize_memory_content(text: str) -> str:
    """The dedupe comparison form: casefolded, whitespace-collapsed, edge
    punctuation stripped. Deterministic and idempotent (the attempt
    evaluator's ``normalize_answer`` is the in-repo precedent)."""

    collapsed = _WHITESPACE.sub(" ", text).strip()
    stripped = _EDGE_PUNCTUATION.sub("", collapsed)
    return stripped.casefold()


def memory_id_for(proposal: RelationshipMemoryProposal) -> RelationshipMemoryId:
    """``rm-<opaque digest>`` — deterministic per (scope, type, content, turn).

    DATA_MODEL §1.2 stable opaque ids: the id embeds no readable value and is
    derived only from the memory's own identity, so a crash-retry of the same
    write re-derives the same id (the idempotent-replay branch in
    elc.relationship.store) while a differently-identified memory can never
    collide with it.
    """

    payload = "\x1f".join(
        (
            str(proposal.persona_id),
            str(proposal.user_id),
            proposal.memory_type.value,
            normalize_memory_content(proposal.content),
            (
                ""
                if proposal.source_turn_id is None
                else str(proposal.source_turn_id)
            ),
        )
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]
    return RelationshipMemoryId(f"rm-{digest}")


def _validation_error(message: str) -> DomainError:
    return DomainError(code=DomainErrorCode.VALIDATION_FAILED, message=message)


def validate_proposal(proposal: RelationshipMemoryProposal) -> DomainError | None:
    """The §5 validate rule set (module docstring); ``None`` = may proceed."""

    if proposal.memory_type.value not in CANONICAL_MEMORY_TYPES:
        return _validation_error(
            f"memory_type {proposal.memory_type.value!r} is not one of the"
            f" canonical §5 memory types {CANONICAL_MEMORY_TYPES}"
        )
    if proposal.provenance.value not in CANONICAL_MEMORY_PROVENANCE:
        return _validation_error(
            f"provenance {proposal.provenance.value!r} is not one of the"
            " canonical §5 provenance words"
            f" {CANONICAL_MEMORY_PROVENANCE}"
        )
    if not proposal.content.strip():
        return _validation_error(
            "canonical_content is empty — a memory that asserts nothing is"
            " not a memory (§5 write flow)"
        )
    if not proposal.recorder_version.strip():
        return _validation_error(
            "recorder_version is empty — DATA_MODEL §1.4 'version every"
            " derived model'; the durable column is NOT NULL and an empty"
            " version is not a version (review F6)"
        )
    if not str(proposal.persona_id).strip() or not str(proposal.user_id).strip():
        return _validation_error(
            "the §5 unit is Persona × User: both scope legs must be present"
        )
    if not proposal.provenance_refs:
        return _validation_error(
            "provenance_refs is empty — BF-05 §17 'Provenance 是删除的前提'"
            ": a relationship memory must be traceable to what it was read"
            " from"
        )
    user_stated = proposal.provenance is MemoryProvenance.USER_STATED_FACT
    if user_stated:
        if proposal.source_turn_id is None or str(
            proposal.source_turn_id
        ) not in proposal.provenance_refs:
            return _validation_error(
                "a USER_STATED_FACT must carry the real user turn it was read"
                " from (BF-05 §7: 'USER_STATED_FACT 必须有真实 UserTurn"
                " provenance'); a persona-generated claim about what the user"
                " said is at most a PERSONA_IMPRESSION"
            )
    if proposal.memory_type is RelationshipMemoryType.USER_STATED_FACT and (
        not user_stated
    ):
        return _validation_error(
            "a memory typed USER_STATED_FACT states what the user said, so its"
            " provenance is USER_STATED_FACT — a persona impression must not"
            " be laundered into the user's own words (BF-05 §7)"
        )
    if user_stated and proposal.confidence is not None:
        return _validation_error(
            "confidence must be None for a user-stated memory (DATA_MODEL §23"
            " 'confidence?'; DOMAIN_MODEL §5 'Important distinction'): a"
            " statement is not a scored inference"
        )
    if (
        proposal.provenance is MemoryProvenance.SYSTEM_INFERRED_FACT
        and proposal.confidence is None
    ):
        return _validation_error(
            "a SYSTEM_INFERRED_FACT must carry its confidence (DATA_MODEL §23"
            " 'confidence?'): an inference without its score is not"
            " reviewable"
        )
    if proposal.confidence is not None and not (0.0 <= proposal.confidence <= 1.0):
        return _validation_error(
            f"confidence {proposal.confidence!r} is outside [0.0, 1.0]"
        )
    if proposal.sensitivity_class.value not in SENSITIVITY_CLASSES:
        return _validation_error(
            f"sensitivity_class {proposal.sensitivity_class.value!r} is not a"
            " BF-05 class legal for relationship memory"
            f" {SENSITIVITY_CLASSES}"
        )
    if (
        proposal.persistence_authorization.value
        not in PERSISTENCE_AUTHORIZATIONS
    ):
        return _validation_error(
            "persistence_authorization"
            f" {proposal.persistence_authorization.value!r} is not a BF-05"
            f" authorization word {PERSISTENCE_AUTHORIZATIONS}"
        )
    if proposal.supersedes_memory_id is not None and (
        str(proposal.supersedes_memory_id) == str(memory_id_for(proposal))
    ):
        return _validation_error("a memory never supersedes itself")
    return None


def find_duplicate(
    *,
    memory_type: RelationshipMemoryType,
    canonical_content: str,
    existing: Sequence[RelationshipMemoryRecord],
) -> RelationshipMemoryRecord | None:
    """The dedupe rule: the first ACTIVE row of the same memory type whose
    canonical content matches after normalization (module docstring).

    The caller passes the rows of one (persona, user) scope — the scope leg
    is the read's, not this function's — in durable order; the memory_type
    leg is re-checked here. ACTIVE rows only: a superseded row is history
    (docs/DATA_MODEL.md §1.3 append-first), so re-stating a corrected fact
    is a new memory rather than a rewrite of the past.
    """

    normalized = normalize_memory_content(canonical_content)
    for row in existing:
        if row.memory_type is not memory_type:
            continue
        if row.status is not MemoryStatus.ACTIVE:
            continue
        if normalize_memory_content(row.canonical_content) == normalized:
            return row
    return None
