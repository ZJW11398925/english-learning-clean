"""Production ``TeachingTargetProvider`` over the built content.db artifact.

``elc.teaching.targets.TeachingTargetProvider`` is the Gate's narrow target
port (P3-1A): one ``(target_type, target_id)`` → one
:class:`elc.teaching.targets.TeachingTargetView`, and the port never decides —
the Gate owns admissibility (docs/DOMAIN_MODEL.md §2), the ladder and the
evaluator own the attempt. Phase 3 served that port from
``tests/phase3/target_fixtures.py``; P5-1 replaces the fixture with this
provider over the real supply chain:

    content_src/* + curriculum/*  →  elc.content.build  →  content.db
        →  elc.content.store (read-only)  →  elc.curriculum.store
        →  this provider  →  Gate facts

The port's three outcome classes are mapped from artifact facts alone
(docs/DATA_MODEL.md §14.1 status vocabulary; the mapping is the whole
contract):

===================  ======================  =======================
artifact state       provider answer         Gate
===================  ======================  =======================
entity row absent,   ``Err(NOT_FOUND)``      MISSING / INVALID →
or the id is not a                           DENY TARGET_INVALID
target of the                                (deterministic)
requested
``target_type``
entity row present,  ``Ok(view)``            ALLOW path
§24.11               VALID / VALID
``CANONICAL_APPROVED``
entity row present,  ``Ok(view)``            DENY TARGET_INVALID
DEPRECATED /         DEPRECATED / INVALID    (deterministic)
REPLACED (§24.11
retired)
entity row present,  ``Ok(view)``            DENY (deterministic):
any other §24.11     INVALID / INVALID       "candidate content
status                                       excluded"
artifact missing /   ``Err(DEPENDENCY_      UNKNOWN → DEGRADED
unreadable / not     UNAVAILABLE)``          (never a synthetic
the built schema                             DENY)
===================  ======================  =======================

Three consequences worth stating because they are the discipline, not details:

- ``content_status`` is VALID exactly when the entity is supply-eligible
  (elc.content.types.supply_eligible); ``target_status`` additionally names
  *why* a non-eligible target is not eligible — retired (DEPRECATED) and
  never-approved (INVALID) stay distinguishable in the Gate's trace instead of
  collapsing into one word;
- an unknown id and a kind mismatch are both deterministically "no such
  target" (the pair the caller asked for does not exist), which is exactly the
  port's NOT_FOUND meaning — the provider never reports "MISSING" itself;
- a broken artifact is **never** laundered into a deterministic DENY: the
  provider answers "I cannot judge" (the resolver-side failure the port
  documents) and the Gate degrades. The same rule covers an entity whose
  per-entity payload rows are absent, because the build writes the four blocks
  together (elc.content.build ``_ENTITY_KEYS``) — such an artifact is not the
  built schema this reader may take a partial answer out of
  (elc.content.store.ContentStoreError says the same thing for tables).

What this provider deliberately is **not**: a supply filter that hides
unapproved content. "Excluded" is a property of *supply sets*
(elc.curriculum.store.CurriculumContentStore.supply_entity_ids) — an excluded
entity stays resolvable and its exclusion stays visible, which is what lets a
user request on it end as a canonical DENY with a true reason.

Not re-exported from ``elc.curriculum.__init__``: this module imports
elc.curriculum.store, so an init-level re-export inherits that cycle
(``elc.content.queries`` runs the curriculum ``__init__`` first — see
elc.curriculum.store's note). Import it by its full path.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from elc.content.store import ContentStore, ContentStoreError
from elc.content.types import RETIRED_LIFECYCLE_STATUSES, supply_eligible
from elc.curriculum.store import CurriculumContentStore
from elc.platform.types import (
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    Result,
)
from elc.teaching.targets import TeachingTargetView

__all__ = ["ContentBackedTeachingTargetProvider"]


def _error(code: DomainErrorCode, message: str) -> Err[object]:
    return Err(DomainError(code=code, message=message))


def _statuses_for(lifecycle_status: str) -> tuple[str, str]:
    """The port's ``(target_status, content_status)`` facts for one §24.11
    lifecycle value (see the module docstring's table).

    One rule: ``content_status`` is VALID exactly when the entity may enter
    supply; ``target_status`` names the retired case separately so the Gate's
    trace keeps saying which of the two non-valid states happened.
    """

    if supply_eligible(lifecycle_status):
        return "VALID", "VALID"
    if lifecycle_status in RETIRED_LIFECYCLE_STATUSES:
        return "DEPRECATED", "INVALID"
    return "INVALID", "INVALID"


class ContentBackedTeachingTargetProvider:
    """The production target provider: content.db in, Gate facts out.

    Constructed either over a path (the artifact is opened lazily on the first
    resolve, so a missing or unreadable content.db surfaces as a port-level
    ``Err`` — the Gate's DEGRADED path — instead of a construction failure
    that would leave the whole assembly unusable) or over an already-open
    :class:`elc.curriculum.store.CurriculumContentStore` (a caller that owns
    the connection; this provider then does not close it).

    ``resolve`` is the only public face the port declares; it never raises for
    an artifact problem, and it never decides.
    """

    def __init__(self, source: str | Path | CurriculumContentStore) -> None:
        if isinstance(source, CurriculumContentStore):
            self._supply: CurriculumContentStore | None = source
            self._path: Path | None = None
            self._owns_supply = False
        else:
            self._supply = None
            self._path = Path(source)
            self._owns_supply = False

    # -- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        """Release the artifact connection this provider opened itself.

        A caller-supplied supply stays the caller's to close.
        """

        if self._supply is not None and self._owns_supply:
            self._supply.close()
            self._supply = None
            self._owns_supply = False

    def _supply_result(self) -> Result[CurriculumContentStore]:
        """The open supply, or the port-level "cannot answer" error."""

        if self._supply is not None:
            return Ok(self._supply)
        path = self._path
        assert path is not None, "provider has neither a supply nor a path"
        try:
            store = ContentStore(path)
        except (ContentStoreError, sqlite3.Error, OSError) as exc:
            return _error(
                DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                f"content.db unavailable for target resolution: {exc!r}",
            )
        self._supply = CurriculumContentStore(store)
        self._owns_supply = True
        return Ok(self._supply)

    # -- the port ----------------------------------------------------------

    def resolve(
        self, target_type: str, target_id: str
    ) -> Result[TeachingTargetView]:
        """Resolve one target (see the module docstring's outcome table).

        ``Ok(view)`` — the facts are known (the status fields may still be
        non-VALID, which the Gate turns into its own deterministic DENY);
        ``Err(NOT_FOUND)`` — no such target; any other ``Err`` — this resolver
        could not answer (the Gate degrades).
        """

        supply = self._supply_result()
        if isinstance(supply, Err):
            return supply
        return self._resolve(supply.value, target_type, target_id)

    def _resolve(
        self,
        supply: CurriculumContentStore,
        target_type: str,
        target_id: str,
    ) -> Result[TeachingTargetView]:
        resource = supply.get_resource(target_id)
        if isinstance(resource, Err):
            # NOT_FOUND stays NOT_FOUND (deterministic); anything else is the
            # resolver being unable to answer.
            if resource.error.code is DomainErrorCode.NOT_FOUND:
                return _error(
                    DomainErrorCode.NOT_FOUND,
                    f"no content entity {target_id!r} in content.db",
                )
            return resource
        target = supply.get_target(target_id)
        if isinstance(target, Err):
            return _error(
                DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                f"content entity {target_id!r} carries no §11 target row: "
                "the artifact is not the built schema",
            )
        if target.value.target_type != target_type:
            return _error(
                DomainErrorCode.NOT_FOUND,
                f"{target_id!r} declares target_type "
                f"{target.value.target_type!r}, not {target_type!r}",
            )
        teaching = supply.get_teaching_content(target_id)
        if isinstance(teaching, Err):
            return _error(
                DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                f"content entity {target_id!r} carries no teaching payload: "
                "the artifact is not the built schema",
            )

        target_status, content_status = _statuses_for(
            resource.value.lifecycle_status
        )
        return Ok(
            TeachingTargetView(
                target_type=target.value.target_type,
                target_id=target_id,
                target_status=target_status,
                content_status=content_status,
                target_mode=target.value.target_mode,
                learning_intent=target.value.learning_intent,
                evidence_modality=target.value.evidence_modality,
                hint_ladder=teaching.value.hint_ladder,
                reveal_form=teaching.value.reveal_form,
                canonical_forms=teaching.value.canonical_forms,
                alternative_realizations=(
                    teaching.value.alternative_realizations
                ),
                required_slots=teaching.value.required_slots,
                capability_linkage=teaching.value.capability_linkage,
            )
        )
