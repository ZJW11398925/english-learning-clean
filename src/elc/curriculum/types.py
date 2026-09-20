"""Curriculum domain — curriculum graph + capability registry.

Owns (docs/DOMAIN_MODEL.md §7): Curriculum Graph, capability registry,
prerequisites, core tier, curriculum links, goal/assessment mappings.
Does NOT own: content resources (Content Library), mastery (Learning),
review scheduling (Scheduler).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from elc.platform.types import CapabilityId, CurriculumNodeId, CurriculumVersion


class CapabilityFamily(StrEnum):
    """docs/DOMAIN_MODEL.md §7 — V2.1: 14 families / 89 Level-2 capabilities."""

    REF = "REF"
    NAR = "NAR"
    EXPL = "EXPL"
    EVAL = "EVAL"
    STANCE = "STANCE"
    PLAN = "PLAN"
    NORM = "NORM"
    AFFECT = "AFFECT"
    SOCIAL = "SOCIAL"
    INFO = "INFO"
    INTERACT = "INTERACT"
    DISC = "DISC"
    MEDIATE = "MEDIATE"
    STYLE = "STYLE"


class CurriculumEdgeType(StrEnum):
    """docs/DOMAIN_MODEL.md §7 edges."""

    DECOMPOSES_INTO = "DECOMPOSES_INTO"
    REALIZED_BY = "REALIZED_BY"
    SUPPORTS = "SUPPORTS"
    PREREQUISITE_FOR = "PREREQUISITE_FOR"
    REFINES = "REFINES"
    ALTERNATIVE_TO = "ALTERNATIVE_TO"
    CONTRASTS_WITH = "CONTRASTS_WITH"
    REGISTER_VARIANT_OF = "REGISTER_VARIANT_OF"
    COMMONLY_CONFUSED_WITH = "COMMONLY_CONFUSED_WITH"
    GENERALIZES_TO = "GENERALIZES_TO"
    ELICITABLE_IN = "ELICITABLE_IN"


class PrerequisiteStrength(StrEnum):
    """HARD-prerequisite subgraph must stay a DAG (docs/DOMAIN_MODEL.md §7)."""

    HARD = "HARD"
    SOFT = "SOFT"
    SCAFFOLDABLE = "SCAFFOLDABLE"


@dataclass(frozen=True)
class CapabilityNodeRecord:
    """One Level-2 capability in the registry."""

    curriculum_node_id: CurriculumNodeId
    capability_id: CapabilityId
    family: CapabilityFamily
    level: int


@dataclass(frozen=True)
class CurriculumEdgeRecord:
    from_node: CurriculumNodeId
    to_node: CurriculumNodeId
    edge_type: CurriculumEdgeType
    prerequisite_strength: PrerequisiteStrength | None


@dataclass(frozen=True)
class CurriculumGraphRecord:
    """Owner schema for the canonical graph (versioned, rebuild-safe)."""

    curriculum_version: CurriculumVersion
    nodes: tuple[CapabilityNodeRecord, ...]
    edges: tuple[CurriculumEdgeRecord, ...]


@dataclass(frozen=True)
class CurriculumCandidateView:
    """Planner input authority (docs/DOMAIN_MODEL.md §10)."""

    curriculum_version: CurriculumVersion
    candidate_node_ids: tuple[CurriculumNodeId, ...]
