"""Relationship domain — Persona×User memory truth (docs/DOMAIN_MODEL.md §5)."""

from elc.relationship.commands import RelationshipCommands
from elc.relationship.controller import RelationshipController
from elc.relationship.episode import (
    EPISODE_ABSENT_BASE_VERSION,
    EPISODE_PROJECTION_VERSION,
    EPISODE_RECENT_EVENT_LIMIT,
    EPISODE_SUMMARY_MAX_UTTERANCES,
    EPISODE_SUMMARY_UTTERANCE_MAX_CHARS,
    EpisodeConversationSource,
    EpisodeRecord,
    EpisodeView,
    episode_id_for,
    episode_version_for,
    rebuild_episode,
)
from elc.relationship.episode_store import SqliteEpisodeStore
from elc.relationship.projection import (
    EpisodeProjectionExecutor,
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
    "EPISODE_ABSENT_BASE_VERSION",
    "EPISODE_PROJECTION_VERSION",
    "EPISODE_RECENT_EVENT_LIMIT",
    "EPISODE_SUMMARY_MAX_UTTERANCES",
    "EPISODE_SUMMARY_UTTERANCE_MAX_CHARS",
    "RELATIONSHIP_RECORDER_ID",
    "RELATIONSHIP_RECORDER_VERSION",
    "RELATIONSHIP_VALIDATOR_ID",
    "RELATIONSHIP_VALIDATOR_VERSION",
    "CommandTurnClassifier",
    "EpisodeConversationSource",
    "EpisodeProjectionExecutor",
    "EpisodeRecord",
    "EpisodeView",
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
    "SqliteEpisodeStore",
    "SqliteRelationshipStore",
    "command_turn_memory_refusal",
    "decide_persistence",
    "episode_id_for",
    "episode_version_for",
    "find_duplicate",
    "memory_id_for",
    "normalize_memory_content",
    "rebuild_episode",
    "validate_proposal",
]
