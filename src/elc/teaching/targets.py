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
from elc.teaching.evaluator import AttemptAnswerKey

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
    """One resolved target as the Gate, the ladder, the evaluator and CP2
    need it — a *validity + teaching content* view.

    The validity facts plus the canonical defaults a TeachingMoment stamps
    (DOMAIN_MODEL §11 target_mode / learning_intent; DATA_MODEL §24.14 V1
    evidence modality). It carries no learner state, no priority and no
    priority signal (DOMAIN_MODEL §15: the Gate is not a second Planner).

    Phase 3 P3-1B adds the target's *teaching content* — the P3-1A field
    note above said Phase 5 brings these; the slice needs them earlier
    because the ladder and evaluator v0 are fixture-driven by design
    (TASK-…2.2 ④⑤: "canonical form / alternative realization whitelist /
    required slots / hint ladder / reveal form / capability linkage"):

    - ``hint_ladder`` — the ordered hint rungs (semantic → structural →
      partial form) the presentation ladder walks; the provider never
      picks a stage, it reports the target's validated rungs;
    - ``reveal_form`` — the canonical full form shown by a reveal;
    - ``canonical_forms`` / ``alternative_realizations`` /
      ``required_slots`` — the attempt answer key (elc.teaching.evaluator);
    - ``capability_linkage`` — the CAPABILITY this RESOURCE realizes
      (docs/DATA_MODEL.md §13 REALIZES/SUPPORTS links); it is what lets
      Learning map an alternative realization onto a capability claim.

    All six default to the empty/absent value, so a Phase 5 provider that
    only knows validity facts keeps working unchanged."""

    target_type: str
    target_id: str
    target_status: str
    content_status: str
    target_mode: str
    learning_intent: str
    evidence_modality: str
    hint_ladder: tuple[str, ...] = ()
    reveal_form: str | None = None
    canonical_forms: tuple[str, ...] = ()
    alternative_realizations: tuple[str, ...] = ()
    required_slots: tuple[tuple[str, ...], ...] = ()
    capability_linkage: str | None = None

    def answer_key(self) -> AttemptAnswerKey:
        """The evaluator's view of this target (the evaluator module owns
        the key type; this method only projects the three fields)."""

        return AttemptAnswerKey(
            canonical_forms=self.canonical_forms,
            alternative_realizations=self.alternative_realizations,
            required_slots=self.required_slots,
        )


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
