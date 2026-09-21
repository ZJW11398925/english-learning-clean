"""Relationship domain — Persona×User memory truth (docs/DOMAIN_MODEL.md §5)."""

from elc.relationship.commands import RelationshipCommands
from elc.relationship.controller import RelationshipController
from elc.relationship.queries import RelationshipQueries
from elc.relationship.types import (
    MemoryProvenance,
    MemorySensitivityClass,
    MemoryStatus,
    PersistenceAuthorization,
    RelationshipMemoryProposal,
    RelationshipMemoryRecord,
    RelationshipMemoryType,
    RelationshipView,
)

__all__ = [
    "MemoryProvenance",
    "MemorySensitivityClass",
    "MemoryStatus",
    "PersistenceAuthorization",
    "RelationshipCommands",
    "RelationshipController",
    "RelationshipMemoryProposal",
    "RelationshipMemoryRecord",
    "RelationshipMemoryType",
    "RelationshipQueries",
    "RelationshipView",
]
