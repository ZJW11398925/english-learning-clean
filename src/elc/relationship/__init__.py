"""Relationship domain — Persona×User memory truth (docs/DOMAIN_MODEL.md §5)."""

from elc.relationship.commands import RelationshipCommands
from elc.relationship.controller import RelationshipController
from elc.relationship.queries import RelationshipQueries
from elc.relationship.types import (
    MemoryProvenance,
    MemoryStatus,
    RelationshipMemoryProposal,
    RelationshipMemoryRecord,
    RelationshipMemoryType,
    RelationshipView,
)

__all__ = [
    "MemoryProvenance",
    "MemoryStatus",
    "RelationshipCommands",
    "RelationshipController",
    "RelationshipMemoryProposal",
    "RelationshipMemoryRecord",
    "RelationshipMemoryType",
    "RelationshipQueries",
    "RelationshipView",
]
