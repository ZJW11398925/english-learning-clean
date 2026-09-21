"""Deterministic LEARNING_EVIDENCE analysis producer (Phase 2 P2A; P5-2
extension).

Adjudicated DEC-…eaaa5a1d.26 b: Phase 2's analysis producer is
deterministic — zero model calls, zero randomness, zero wall-clock reads.
The producer extracts a proposal-only descriptor of the turn's observable
behavior from the canonical turn slice (docs/DATA_MODEL.md §3
CanonicalTurnSlice); docs/DATA_MODEL.md §5 keeps AnalysisArtifact proposal-
only ("不是 Domain truth") and docs/DOMAIN_MODEL.md §18 leaves the
VALIDATE / COMMIT / REJECT / ABSTAIN decision to the Learning domain face
(elc.learning.store). The real-LLM analysis phases arrive later; this
module is the durable core's deterministic stand-in.

P5-2 adds one optional input fact: a **target observation** the chat leg
resolved deterministically (elc.learning.target_resolution). When the
caller supplies one, the proposal document additionally records *which*
target, *which* form and *which* rule (`"target"` — the four keys of
elc.learning.target_resolution.resolution_document); when it does not, the
document is byte-identical to the Phase 2 shape, so every P2 assembly and
its pinned payloads are unchanged. The document stays *facts only*: the
conversion into a §6 claim is Learning's (elc.learning.silent_claim, applied
at the CP1 commit) — the teaching-evidence pattern, where the source reports
the facts and Learning decides what they are worth as evidence.

Determinism contract (tested in tests/phase2):
- ids are content-derived hashes (docs/DATA_MODEL.md §1.2 stable opaque
  IDs; recovery re-entry re-derives the same ids, which is what makes
  "crash after CP0 → continue from analysis" idempotent, RUNTIME §23);
- ``structured_proposal`` is canonical JSON (sorted keys, fixed
  separators) over turn-derived values only — no clock, no RNG, no
  provider.

This module is pure: no sqlite3, no SQL, no DB call surface.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from elc.conversation.types import CanonicalTurnSlice
from elc.learning.target_resolution import (
    ResolvedTarget,
    resolution_document,
)
from elc.platform.types import (
    AnalysisId,
    EvidenceGroupId,
    Result,
    TurnId,
)

__all__ = [
    "ANALYSIS_TYPE_LEARNING_EVIDENCE",
    "DETERMINISTIC_ANALYSIS_PRODUCER_ID",
    "DETERMINISTIC_ANALYSIS_PRODUCER_VERSION",
    "DETERMINISTIC_EVALUATOR_ID",
    "LearningEvidenceProposal",
    "LearningTurnAnalysis",
    "deterministic_analysis_id",
    "deterministic_evidence_commit_id",
    "deterministic_evidence_group_id",
    "produce_learning_evidence_proposal",
]

#: AnalysisArtifact.analysis_type for this producer (DATA_MODEL §5).
ANALYSIS_TYPE_LEARNING_EVIDENCE = "LEARNING_EVIDENCE"

#: Deterministic producer identity (TASK-…30 deliverable ③: a named
#: deterministic producer; the model-assisted producers arrive later).
DETERMINISTIC_ANALYSIS_PRODUCER_ID = "deterministic-learning-evidence"
DETERMINISTIC_ANALYSIS_PRODUCER_VERSION = "deterministic-v1"

#: Evaluator identity stamped on claims/groups produced by the P2A
#: deterministic pipeline (DATA_MODEL §6 evaluator_id/evaluator_version).
DETERMINISTIC_EVALUATOR_ID = "deterministic-learning-evidence"

#: Confidence of a deterministic extraction: no model uncertainty.
DETERMINISTIC_PRODUCER_CONFIDENCE = 1.0


def _digest(*parts: str) -> str:
    hasher = hashlib.sha256()
    for part in parts:
        hasher.update(part.encode("utf-8"))
        hasher.update(b"\x1f")  # unambiguous field separator
    return hasher.hexdigest()


def deterministic_analysis_id(turn_id: TurnId) -> AnalysisId:
    """Stable analysis id for one turn's LEARNING_EVIDENCE artifact.

    Derived from (producer, turn) so a re-run after a crash re-derives
    the identical id — physical idempotency for RA §23 "crash after CP0
    从 analysis 继续" (the unique (turn_id, analysis_type, producer_id)
    backs it durably).
    """

    return AnalysisId(
        f"an-{_digest(DETERMINISTIC_ANALYSIS_PRODUCER_ID, turn_id)[:24]}"
    )


def deterministic_evidence_group_id(
    turn_id: TurnId, evidence_modality: str
) -> EvidenceGroupId:
    """Stable group id: one observable behavior per turn × modality
    (DATA_MODEL §6 "一个 observable behavior 对应一个 group")."""

    return EvidenceGroupId(f"eg-{_digest(turn_id, evidence_modality)[:24]}")


def deterministic_evidence_commit_id(group_id: EvidenceGroupId) -> str:
    """Stable CP1 commit id for a group, so replay returns the same
    EvidenceCommitId (RA §23 "crash after CP1 不重复 Evidence")."""

    return f"ec-{_digest(group_id)[:24]}"


@dataclass(frozen=True)
class LearningEvidenceProposal:
    """The deterministic LEARNING_EVIDENCE proposal payload (DATA_MODEL
    §5 structured_proposal, as a typed view before canonical-JSON
    serialization)."""

    analysis_id: AnalysisId
    turn_id: TurnId
    producer_id: str
    producer_version: str
    structured_proposal: str
    confidence: float


def produce_learning_evidence_proposal(
    turn: CanonicalTurnSlice,
    *,
    resolution: ResolvedTarget | None = None,
) -> LearningEvidenceProposal:
    """Extract the turn's observable-behavior descriptor.

    The extraction is deliberately conservative: no curriculum/target
    *judgement* happens here and no model is involved (Phase 5 P5-2 supplies
    the one optional target fact — a deterministic extraction the chat leg
    resolved through the supply read face, elc.learning.silent_evidence), so
    the proposal asserts only what the canonical turn itself carries — the
    utterance hash, its length, the TEXT_PRODUCTION modality (V1 typed chat,
    DATA_MODEL §24.14), whether an observable behavior exists at all
    (non-blank utterance), and, when the caller hands one over, the resolved
    target observation. Target-*bearing* claims are a later producer's job;
    committing a proposal is Learning's decision, not the producer's
    (DOMAIN_MODEL §18).

    ``resolution=None`` (the default, and every Phase 2 caller) produces the
    exact Phase 2 document — no ``"target"`` key, byte-identical payload.
    """

    text = turn.user_turn.raw_content
    proposal: dict[str, object] = {
        "analysis_type": ANALYSIS_TYPE_LEARNING_EVIDENCE,
        "evidence_modality": "TEXT_PRODUCTION",
        "observable": bool(text.strip()),
        "utterance_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "utterance_length": len(text),
    }
    if resolution is not None:
        # Facts only: which target, which form, which rule (P5-2). The claim
        # conversion is Learning's at commit time (elc.learning.silent_claim).
        proposal["target"] = resolution_document(resolution)
    return LearningEvidenceProposal(
        analysis_id=deterministic_analysis_id(turn.turn_id),
        turn_id=turn.turn_id,
        producer_id=DETERMINISTIC_ANALYSIS_PRODUCER_ID,
        producer_version=DETERMINISTIC_ANALYSIS_PRODUCER_VERSION,
        structured_proposal=json.dumps(
            proposal, sort_keys=True, separators=(",", ":")
        ),
        confidence=DETERMINISTIC_PRODUCER_CONFIDENCE,
    )


@runtime_checkable
class LearningTurnAnalysis(Protocol):
    """The turn-scoped learning face the ConversationCoordinator drives
    (RUNTIME_ARCHITECTURE §4 steps 3-4): produce the durable
    LEARNING_EVIDENCE AnalysisArtifact, then hand it to Learning for
    validation + the CP1 commit. Implemented by
    elc.learning.store.SqliteLearningStore and injected into the
    coordinator as a port (TASK-…30 deliverable ⑥); the coordinator stays
    SQL-free (Gate item 2)."""

    def record_learning_analysis(
        self,
        turn: CanonicalTurnSlice,
        *,
        resolution: ResolvedTarget | None = None,
    ) -> Result[LearningEvidenceProposal]:
        """RA §4 step 3: deterministic producer → durable PRODUCED
        artifact; idempotent per (turn, analysis_type, producer).

        ``resolution`` is the P5-2 optional target observation (RA §21: a
        caller that could not resolve one passes ``None`` — the target-less
        Phase 2 proposal). The durable row wins on re-entry: an artifact
        that already exists is replayed as recorded, so a re-run can never
        swap the observed facts under a stable analysis id.
        """
        ...

    def commit_learning_evidence(
        self,
        proposal: LearningEvidenceProposal,
        turn: CanonicalTurnSlice,
        persona_id: str | None = None,
    ) -> Result[str]:
        """RA §4 step 4 / CP1: validate the proposal, commit the
        EvidenceGroup (+ claims), advance the durable evidence watermark,
        mark the artifact COMMITTED — one short transaction."""
        ...
