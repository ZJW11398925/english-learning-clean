"""Relationship domain — Persona×User memory truth (docs/DOMAIN_MODEL.md §5)."""

from elc.relationship.commands import RelationshipCommands
from elc.relationship.controller import RelationshipController
from elc.relationship.projection import (
    RelationshipCandidateProvider,
    RelationshipProjectionExecutor,
)
from elc.relationship.queries import RelationshipQueries
from elc.relationship.recorder import (
    RELATIONSHIP_RECORDER_ID,
    RELATIONSHIP_RECORDER_VERSION,
    CommandTurnClassifier,
    RelationshipMemoryCandidate,
    RelationshipMemoryRefusal,
    RelationshipRecorder,
    RelationshipRecorderKey,
    RelationshipRecorderOutcome,
    command_turn_memory_refusal,
)
from elc.relationship.sensitivity import (
    ALLOW_AFTER_VALIDATION,
    DENY,
    PersistenceDecision,
    decide_persistence,
)
from elc.relationship.store import SqliteRelationshipStore
from elc.relationship.types import (
    MemoryProvenance,
    MemorySensitivityClass,
    MemoryStatus,
    PersistenceAuthorization,
    RelationshipMemoryProposal,
    RelationshipMemoryRecord,
    RelationshipMemorySummaryEntry,
    RelationshipMemoryType,
    RelationshipView,
    SamePersonaExistingRelationshipSummary,
)
from elc.relationship.validation import (
    RELATIONSHIP_VALIDATOR_ID,
    RELATIONSHIP_VALIDATOR_VERSION,
    find_duplicate,
    memory_id_for,
    normalize_memory_content,
    validate_proposal,
)

__all__ = [
    "ALLOW_AFTER_VALIDATION",
    "DENY",
    "RELATIONSHIP_RECORDER_ID",
    "RELATIONSHIP_RECORDER_VERSION",
    "RELATIONSHIP_VALIDATOR_ID",
    "RELATIONSHIP_VALIDATOR_VERSION",
    "CommandTurnClassifier",
    "MemoryProvenance",
    "MemorySensitivityClass",
    "MemoryStatus",
    "PersistenceAuthorization",
    "PersistenceDecision",
    "RelationshipCandidateProvider",
    "RelationshipCommands",
    "RelationshipController",
    "RelationshipMemoryCandidate",
    "RelationshipMemoryProposal",
    "RelationshipMemoryRecord",
    "RelationshipMemoryRefusal",
    "RelationshipMemorySummaryEntry",
    "RelationshipMemoryType",
    "RelationshipProjectionExecutor",
    "RelationshipQueries",
    "RelationshipRecorder",
    "RelationshipRecorderKey",
    "RelationshipRecorderOutcome",
    "RelationshipView",
    "SamePersonaExistingRelationshipSummary",
    "SqliteRelationshipStore",
    "command_turn_memory_refusal",
    "decide_persistence",
    "find_duplicate",
    "memory_id_for",
    "normalize_memory_content",
    "validate_proposal",
]
