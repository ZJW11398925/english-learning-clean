"""Curriculum domain — curriculum graph + capability registry.

docs/DOMAIN_MODEL.md §7. Interfaces here are the only sanctioned boundary;
other packages must depend on these names, not on internal records.
"""

from elc.curriculum.commands import CurriculumCommands
from elc.curriculum.controller import CurriculumController
from elc.curriculum.queries import CurriculumQueries
from elc.curriculum.types import (
    CapabilityFamily,
    CapabilityNodeRecord,
    CurriculumCandidateView,
    CurriculumEdgeRecord,
    CurriculumEdgeType,
    CurriculumGraphRecord,
    PrerequisiteStrength,
)

__all__ = [
    "CapabilityFamily",
    "CapabilityNodeRecord",
    "CurriculumCandidateView",
    "CurriculumCommands",
    "CurriculumController",
    "CurriculumEdgeRecord",
    "CurriculumEdgeType",
    "CurriculumGraphRecord",
    "CurriculumQueries",
    "PrerequisiteStrength",
]
