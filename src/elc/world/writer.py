"""The POV Writer's V3-5 machine face (TASK-OPI-be7b094f…34 / the
opening ruling DEC-OPI-be7b094f…32) — the deterministic guards around
one segment's prose, then the SEGMENT COMMIT.

**What ships here is the structure, not the prose**: the body is the
caller's own text (the LLM-driven writer face — voice-library injection,
craft-law materials, the POV prompt assembly from the dossier and the
cognition view — is registered as a later cut, the same
schema-and-table-side-only scope V3-4 spelled for the Blueprint). The
deterministic guards this face owns:

- **one POV per scene** — the adopted dossier's ``pov_actor_id`` must
  be among its ``participants`` (the schema's own invariant, rechecked
  here: the Writer's discipline is one main POV, no uncontrolled
  head-hopping);
- **the body is non-empty, the language is non-empty** (a segment with
  no prose is no segment);
- **a secret does not leak before its time** — the body must not
  contain a non-empty fragment of the dossier's ``must_hide`` (split by
  line and sentence delimiters — a deterministic guard, deliberately
  not an NLP detector; a hit is refused ``VALIDATION_FAILED`` naming
  the fragment). ``revealable`` is the plan's permission, never an
  obligation: the guard does not require it to appear.

**The provider Writer hard door (V3-5R, TASK-OPI-dc1bafdf…13 /
DEC-OPI-dc1bafdf…11's item 5, the external review)**: the literal
``must_hide`` substring guard above is **not** a POV knowledge firewall
— a semantic rewrite routes around a lexical guard by construction.
The POV-safe compilation this door demands **landed in V3-8c**: the
Writer's inputs are assembled from the POV character's own cognition
view (:func:`elc.world.cognition.v3_cognition_view` — the lineage read
whose layers are canonical-identity judgments) union the dossier —
compiled by :func:`elc.world.providers.pov_context_of` (V3-8a) and
rendered into the real writer's prompt by
:mod:`elc.world.llm_providers` (V3-8c) — so the things the POV could
not know are **not in the prompt at all**; the lexical guard stays as
the second, deterministic guard it honestly is. The user's "好玩"
acceptance still waits on the assembly-side wiring and the Gold
Scenario's two doors.

Then the segment goes to :func:`elc.world.settlement.commit_segment`
in the caller's own posture:

- ``participants`` = the dossier's own tuple (the scene's cast,
  canonical identities);
- ``effects`` = the empty tuple — the deterministic baseline produces
  **no new world-state facts** (the writer's "subsequent non-user
  facts" arm belongs to the LLM writer cut and the V3-6 resolver);
- ``narration`` = the segment's prose — the baseline's chronicle line
  and its prose are the same text (there is no separate chronicle
  summary yet; the LLM writer cut will separate them, and the
  ``world_event`` row is already a distinct durable record).

Refusals are value semantics: everything above is ``VALIDATION_FAILED``
(or the settlement's own refusals riding out unchanged); ``NOT_FOUND``
for a dangling scene. The Writer **never** re-adjudicates a user
behavior (N-INV-002): it renders what is given and settles the new
non-user facts the plan and the rules allow — none, in this baseline.

Discipline: no hidden clock (``now`` is the caller's); no transaction
of its own (the settlement owns NCP-3's one short transaction); no SQL
at all; the Package is not consulted.
"""

from __future__ import annotations

import re
import sqlite3

from elc.platform.types import (
    DomainError,
    DomainErrorCode,
    Err,
    Result,
)
from elc.world.narrative.store import SqliteNarrativeStore
from elc.world.settlement import CommitOutcome, commit_segment
from elc.world.store import SqliteWorldStore

__all__ = ["PovWriter"]

#: The line / sentence delimiters the ``must_hide`` guard splits on
#: (line breaks plus the CJK and Latin sentence punctuation). The split
#: is a deterministic lexical guard — deliberately not a semantic
#: detector — so its refusal stays reproducible for the caller's retry.
_HIDDEN_SPLIT = re.compile(r"[\n\r。！？；.!?;]+")


class PovWriter:
    """The POV Writer over one database — the deterministic baseline:
    validate one segment's prose against the scene's adopted dossier and
    hand it to the SEGMENT COMMIT.

    Construction mirrors the composition root: the caller hands the
    same connection's narrative and world stores (the commit's group
    needs both faces).
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        narrative_store: SqliteNarrativeStore,
        world_store: SqliteWorldStore,
    ) -> None:
        self._conn = conn
        self._narrative = narrative_store
        self._worlds = world_store

    def write_segment(
        self,
        scene_id: str,
        body: str,
        language: str,
        segment_seq: int,
        duration_ticks: int,
        is_last_segment: bool,
        now: str,
        outcome_ref: str | None = None,
    ) -> Result[CommitOutcome]:
        """Write one segment of one scene: the guards above, then the
        segment commit (whose own docstring spells the atomic group,
        the replay law and the remaining refusals). ``is_last_segment``
        marks the scene's final segment — the SCENE COMMIT alias's own
        trigger. ``outcome_ref`` rides straight through to the
        settlement (the V3-6R chain ``intent → adjudication → committed
        action → outcome_ref → passage`` — a continuing segment names
        the ruling it resumes; the settlement checks the reference, the
        forced law and the targeted close)."""

        if not body.strip():
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"segment {segment_seq} of scene {scene_id!r} not"
                        " written: the body is empty — a segment carries"
                        " prose"
                    ),
                )
            )
        if not language.strip():
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"segment {segment_seq} of scene {scene_id!r} not"
                        " written: the language is empty — every passage"
                        " declares its language"
                    ),
                )
            )
        scene = self._narrative.get_scene(scene_id)
        if scene is None:
            return Err(
                DomainError(
                    code=DomainErrorCode.NOT_FOUND,
                    message=(
                        f"segment {segment_seq} not written: scene"
                        f" {scene_id!r} does not exist"
                    ),
                )
            )
        dossier = self._narrative.adopted_dossier(scene_id)
        if dossier is None:
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"scene {scene_id!r} has no ADOPTED Dossier — the"
                        " Writer writes from the current plan (one POV,"
                        " one cast, the scene's own must_hide)"
                    ),
                )
            )
        if dossier.pov_actor_id not in dossier.participants:
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"dossier {dossier.dossier_id!r} is inconsistent:"
                        f" its POV {dossier.pov_actor_id!r} is not among"
                        " its participants — one POV per scene, and the"
                        " POV is present in her own scene"
                    ),
                )
            )
        leaked = _leaking_fragment(body, dossier.must_hide)
        if leaked is not None:
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"segment {segment_seq} of scene {scene_id!r} not"
                        " written: the body leaks a hidden fact — it"
                        f" contains the must_hide fragment {leaked!r}; a"
                        " secret does not leak before its time (rewrite"
                        " without it)"
                    ),
                )
            )
        return commit_segment(
            self._conn,
            narrative_store=self._narrative,
            world_store=self._worlds,
            scene_id=scene_id,
            segment_seq=segment_seq,
            body=body,
            language=language,
            participants=dossier.participants,
            effects=(),
            narration=body,
            duration_ticks=duration_ticks,
            is_last_segment=is_last_segment,
            now=now,
            outcome_ref=outcome_ref,
        )


def _leaking_fragment(body: str, must_hide: str) -> str | None:
    """The first non-empty ``must_hide`` fragment the body contains, or
    ``None`` — the deterministic secret-leak guard (see the module
    docstring for its shape and its deliberate limits)."""

    for fragment in _HIDDEN_SPLIT.split(must_hide):
        fragment = fragment.strip()
        if fragment and fragment in body:
            return fragment
    return None
