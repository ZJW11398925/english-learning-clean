"""The natural-conversation silent-evidence source (P5-2, the chat leg).

docs/PRODUCT_CONTRACT.md §2.4 + P-INV-009 make a natural conversation turn a
complete product state: the user may just talk. This module is the chat
leg's *observation* half — one optional port the coordinator asks, on every
normal persona turn, "did this turn use a form of a supply-eligible target?":

    utterance + content.db supply facts
        → elc.learning.target_resolution.resolve_target  (pure extraction)
        → ResolvedTarget  or  NO_TARGET

The answer then rides the existing learning chain: the turn's durable
LEARNING_EVIDENCE proposal carries the observation
(elc.learning.analysis.produce_learning_evidence_proposal's ``resolution``),
and the CP1 commit turns it into one target-specific Performance Evidence
claim (docs/DOMAIN_MODEL.md §6, elc.learning.silent_claim) in the same
evidence group as the turn — one observable behavior, one group
(DATA_MODEL §6; the group's unique key is (turn, modality), so there is no
second group to invent). **No TeachingMoment, no Gate decision and no
Planner choice exists anywhere on the path.** The evidence is "silent" in
exactly the product sense: the system observed the learner use the form in
free conversation; it did not teach, prompt or interrupt.

**前置裁决 (P5-2, inherited from the slice's task book).** The §8.1 default
readiness threshold (docs/PRODUCT_CONTRACT.md §8.1 R0/R1 ⇒ not in the
automatic Teaching Frontier) constrains the **Planner automatic teaching
face**. It does not constrain the **evidence-forming face** — this slice is
allowed to form silent evidence on an R1 target (the corpus stops at R1, so
no target would be reachable otherwise), and it must not, and does not, open
any automatic teaching selection (that stays Phase 8). Precisely: this
module's import graph reaches elc.curriculum.readiness (through
elc.curriculum.store), and it **never calls a readiness judgment** — no
readiness value is read, judged or used as a filter anywhere on this path.

**False-positive boundary (declared).** What this face can match is bounded
by the resolver's rules, and the weakest of them is named:
:func:`elc.learning.target_resolution.slots_can_discriminate` — a slot key
that is a single one-token group ("see", "mean", "meeting") is a bare word
check and never drives a resolution; a key needs ≥2 groups or a multi-token
group to engage the slot path at all. That is the first declared input to the
§8.1 R4 detection-policy / false-positive-boundary ladder, not a measured
false-positive rate: a rate needs the detection policy and its fixtures.

**Trust boundary.** The resolution this face hands over is *assumed* to come
from a supply read face of this module's own shape
(:class:`ContentBackedSilentTargets` over :class:`ContentBackedTargetSupply`);
the learning side that consumes it does not re-check supply and never reads
content.db (the claim conversion in elc.learning.silent_claim is pure, and
the store commits what the durable document says). A caller that fabricates a
resolution document can make the kernel commit a claim the corpus does not
support — the read face, not the kernel, is the supply gate (the same
division of labour as the teaching provider).

**Supply gate and degradation (RA §21).**

- the read face is :class:`ContentBackedTargetSupply` over the built
  content.db: only entities the §24.11 supply filter admits
  (``CANONICAL_APPROVED``; elc.curriculum.store.supply_entity_ids) become
  match candidates, so a model-generated candidate or any other unapproved
  entity can never be resolved onto (IMPLEMENTATION_PLAN §6 "candidate
  content excluded");
- an entity whose §11 target row declares a kind outside the canonical pair
  is skipped (never a match candidate), and one that carries no §11 target
  row or no teaching payload makes the artifact "not the built schema" — an
  ``Err`` (the provider precedent), never a partial answer;
- a missing/unreadable content.db is ``Err(DEPENDENCY_UNAVAILABLE)`` at the
  read face and **degrades to NO_TARGET at the port**: the leg writes
  nothing, the chat continues (RA §21 "Learning commit unavailable … normal
  persona"). "Could not answer" and "answered nothing" stay different facts
  *inside* this module; a caller only ever sees NO_TARGET.

Not re-exported from ``elc.learning.__init__``: this module imports
elc.curriculum.store (the supply read face), and an init-level re-export
would drag the content read chain into every ``import elc.learning`` — the
P5-1 precedent (elc.curriculum.store / elc.curriculum.provider are imported
by full path for the same reason). Import it by its full path.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Protocol, runtime_checkable

from elc.content.store import ContentStore, ContentStoreError
from elc.conversation.types import CanonicalTurnSlice
from elc.curriculum.store import CurriculumContentStore
from elc.learning.target_resolution import (
    CANONICAL_TARGET_TYPES,
    ResolvedTarget,
    TargetSupplyFacts,
    resolve_target,
)
from elc.platform.types import (
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    Result,
)

__all__ = [
    "ContentBackedSilentTargets",
    "ContentBackedTargetSupply",
    "SilentEvidenceSource",
]


def _unavailable(message: str) -> Err[object]:
    return Err(
        DomainError(
            code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
            message=message,
        )
    )


class ContentBackedTargetSupply:
    """The supply read face: built content.db → §24.11-filtered facts.

    Constructed either over a path (the artifact is opened lazily on the
    first read, so a missing or unreadable content.db surfaces as an ``Err``
    — the degradation RA §21 asks for — instead of a construction failure
    that would leave the whole assembly unusable) or over an already-open
    :class:`elc.curriculum.store.CurriculumContentStore` (a caller that owns
    the connection; this reader then does not close it). The shape is the
    teaching provider's (elc.curriculum.provider), for the same reason.

    The §24.11 filter is *read* from the curriculum supply face
    (``supply_entity_ids`` — the one place the filter is applied, so this
    reader and the planner/teaching faces cannot drift), and this reader adds
    the resolver's own input contract: the §11 target kind and the §24.5
    teaching payload.
    """

    def __init__(self, source: str | Path | CurriculumContentStore) -> None:
        if isinstance(source, CurriculumContentStore):
            self._supply: CurriculumContentStore | None = source
            self._path: Path | None = None
        else:
            self._supply = None
            self._path = Path(source)

    # -- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        """Release the artifact connection this reader opened itself.

        A caller-supplied supply stays the caller's to close.
        """

        if self._supply is not None and self._path is not None:
            self._supply.close()
            self._supply = None

    def _supply_result(self) -> Result[CurriculumContentStore]:
        if self._supply is not None:
            return Ok(self._supply)
        path = self._path
        assert path is not None, "supply has neither a store nor a path"
        try:
            store = ContentStore(path)
        except (ContentStoreError, sqlite3.Error, OSError) as exc:
            return _unavailable(
                f"content.db unavailable for target resolution: {exc!r}"
            )
        self._supply = CurriculumContentStore(store)
        return Ok(self._supply)

    # -- the read ----------------------------------------------------------

    def facts(self) -> Result[tuple[TargetSupplyFacts, ...]]:
        """Every supply-eligible target as resolver input, in artifact order.

        Deterministic: the eligible id order comes from the artifact
        (``content_entity`` insertion order), and every fact carries the
        §24.5 form/slot payload verbatim. A non-canonical §11 kind is
        skipped (the entity stays readable everywhere else — excluded ≠
        deleted); an entity with no §11 target row or no teaching payload
        makes the artifact "not the built schema" and is an ``Err`` — never
        a partial answer.
        """

        supply_result = self._supply_result()
        if isinstance(supply_result, Err):
            return supply_result
        supply = supply_result.value
        eligible = supply.supply_entity_ids()
        if isinstance(eligible, Err):
            return eligible
        facts: list[TargetSupplyFacts] = []
        for entity_id in eligible.value:
            identifier = str(entity_id)
            target = supply.get_target(identifier)
            if isinstance(target, Err):
                if target.error.code is DomainErrorCode.NOT_FOUND:
                    return _unavailable(
                        f"content entity {identifier!r} carries no §11"
                        " target row: the artifact is not the built schema"
                    )
                return target
            if target.value.target_type not in CANONICAL_TARGET_TYPES:
                continue
            teaching = supply.get_teaching_content(identifier)
            if isinstance(teaching, Err):
                return teaching
            facts.append(
                TargetSupplyFacts(
                    target_type=target.value.target_type,
                    target_id=identifier,
                    canonical_forms=teaching.value.canonical_forms,
                    alternative_realizations=(
                        teaching.value.alternative_realizations
                    ),
                    required_slots=teaching.value.required_slots,
                )
            )
        return Ok(tuple(facts))


@runtime_checkable
class SilentEvidenceSource(Protocol):
    """The chat-leg port the coordinator drives (P5-2).

    One call per turn, inside the RA §4 step 3 slot (before the durable
    proposal is recorded, because the observation is *part of* what the
    proposal says about the turn). Every failure mode answers ``None`` — a
    miss (:data:`NO_TARGET`), a broken supply, an exception — which is the
    RA §21 best-effort shape: no claim this turn, never a blocked
    conversation. Implementations should not raise; the coordinator keeps
    its own guard anyway (an exception is a missing claim, not the turn's
    failure).
    """

    def resolve_turn(self, turn: CanonicalTurnSlice) -> ResolvedTarget | None:
        ...


class ContentBackedSilentTargets:
    """The production silent-evidence source: content.db supply in, one
    resolution (or NO_TARGET) out.

    The whole read path is :class:`ContentBackedTargetSupply` →
    ``target_resolution.resolve_target``; this class only applies the
    degradation rule — a supply it cannot read is NO_TARGET, not an error
    channel — and it owns nothing else (the commit and the rebuild are the
    learning chain's, driven by the coordinator).
    """

    def __init__(self, supply: ContentBackedTargetSupply) -> None:
        self._supply = supply

    def resolve_turn(
        self, turn: CanonicalTurnSlice
    ) -> ResolvedTarget | None:
        facts = self._supply.facts()
        if isinstance(facts, Err):
            # RA §21: a supply this face cannot read is NO_TARGET, not a
            # blocked conversation. The chat leg has already happened.
            return None
        return resolve_target(turn.user_turn.raw_content, facts.value)
