"""Teaching target resolution port (Phase 3 P3-1A, TASK-…17 ③/⑦).

The Gate's target/content-validity family needs exactly one fact pair for
one target — is the target itself teachable, is its content usable. The
Curriculum/Content domains do not exist as durable stores in Phase 3
(Phase 5 brings ``CurriculumCandidateView`` / ``content.db``), so the Gate
consumes a narrow port instead of reaching into a domain: a provider
resolves ``(target_type, target_id)`` into one :class:`TeachingTargetView`.

Vocabulary (docs/DATA_MODEL.md §14.1 gate_execution_status semantics and
the frozen BF-03 v1.1 reference's critical-state sets):

- target status: VALID | INVALID | DEPRECATED | MISSING | UNKNOWN
  (INVALID/DEPRECATED/MISSING are deterministic → Gate DENY TARGET_INVALID;
  UNKNOWN is "cannot judge" → Gate DEGRADED, never a synthetic DENY);
- content status: VALID | INVALID | UNKNOWN
  (INVALID → DENY CONTENT_INVALID; UNKNOWN → DEGRADED).

A provider Err with ``DomainErrorCode.NOT_FOUND`` means "no such target"
— a deterministic parse failure → DENY TARGET_INVALID. Any other Err means
the resolver itself could not answer → the fact is UNKNOWN → DEGRADED.
The port never decides: it reports what it knows, and the Gate owns the
admissibility decision (DOMAIN_MODEL §2 authority matrix).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from elc.platform.types import Result

__all__ = [
    "CONTENT_STATUSES",
    "TARGET_STATUSES",
    "TeachingTargetProvider",
    "TeachingTargetView",
]

#: docs/DATA_MODEL.md §14.1 target validity facts (BF-03 v1.1
#: reference ``target_status`` set, word for word).
TARGET_STATUSES = ("VALID", "INVALID", "DEPRECATED", "MISSING", "UNKNOWN")

#: docs/DATA_MODEL.md §14.1 content validity facts (BF-03 v1.1
#: reference ``content_status`` set, word for word).
CONTENT_STATUSES = ("VALID", "INVALID", "UNKNOWN")

#: The two claim target scopes (docs/DOMAIN_MODEL.md §6: every claim points
#: at RESOURCE or CAPABILITY; a TeachingMoment focuses the same pair).
TARGET_TYPES = ("RESOURCE", "CAPABILITY")


@dataclass(frozen=True)
class TeachingTargetView:
    """One resolved target as the Gate and CP2 need it — deliberately
    narrow: validity facts plus the canonical defaults a TeachingMoment
    stamps (DOMAIN_MODEL §11 target_mode / learning_intent; DATA_MODEL
    §24.14 V1 evidence modality). It carries no learner state, no
    priority and no teaching text (DOMAIN_MODEL §15: the Gate is not a
    second Planner)."""

    target_type: str
    target_id: str
    target_status: str
    content_status: str
    target_mode: str
    learning_intent: str
    evidence_modality: str


@runtime_checkable
class TeachingTargetProvider(Protocol):
    """Narrow resolver port (implemented by the Phase 3 test fixture
    provider over the 10–20 validated target fixtures; Phase 5 replaces it
    with the Curriculum/Content runtime views)."""

    def resolve(
        self, target_type: str, target_id: str
    ) -> Result[TeachingTargetView]:
        """Resolve one target.

        Ok(view) — the facts are known (status fields may still be UNKNOWN,
        which the Gate degrades on); Err(NOT_FOUND) — the target does not
        exist (deterministic: DENY TARGET_INVALID); any other Err — the
        resolver could not answer (Gate DEGRADED, never a synthetic DENY).
        """
        ...
