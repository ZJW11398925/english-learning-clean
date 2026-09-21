"""SQLite durable store for the Learning evidence kernel (Phase 2 P2A).

TASK-OPI-eaaa5a1d-7ac7-4746-bcdf-c02bc9147492.30 deliverable ②/③/④/⑤:
the durable implementation behind ``LearningCommands`` /
``LearningQueries`` (elc.learning.commands / elc.learning.queries) plus
the turn-scoped ``LearningTurnAnalysis`` face the ConversationCoordinator
drives (elc.learning.analysis). Persistence lives in the learning domain
package following the elc.conversation.store precedent (never in
``elc.runtime`` — Gate item 2 keeps the orchestrator SQL-free;
docs/DOMAIN_MODEL.md §16 D-INV-001).

Commit-unit discipline:
- CP1 (docs/RUNTIME_ARCHITECTURE.md §6): validation + EvidenceGroup /
  EvidenceClaim inserts + the evidence_watermark advance + the artifact
  COMMITTED flip run inside ONE ``short_transaction``
  (elc.platform.db.tx.short_transaction) — no half-committed window
  (R-INV-001; "Crash after CP1 不重复 Evidence", RA §22/§23).
- Idempotency: replaying a committed group returns the original
  EvidenceCommitId and writes nothing; the deterministic ids
  (elc.learning.analysis) make coordinator re-entry re-derive the same
  physical keys.
- The watermark storage face is the ``evidence_watermark`` table
  (migration 0004): one row per user_scope_id, monotonically increasing,
  bumped inside the same CP1 transaction. The watermark semantics is the
  durable EVIDENCE-CHANGE sequence number (P2B F2, adjudicated in the
  mother decision DEC-…eaaa5a1d.26): commit / supersede / invalidate all
  advance it — any durable change to the estimating (ACTIVE) claim set
  moves the sequence. P2B's LearnerTargetState / LearningSnapshot
  (DATA_MODEL §11/§12) consume it as the projection's as-of stamp.
- epoch fencing mirrors elc.conversation.store (RA §24).

Phase 2 P2B (TASK-…44): the Estimator lives in
elc.learning.estimator (BF-01 v1.1, zero behavioral_baselines imports);
``rebuild_learner_state`` recomputes the materialized
LearnerTargetState projection from ACTIVE claims and the three
``LearningQueries`` faces read it (migration 0005 stores one §11
document row per user_scope × target_type × target_id × modality — a
deletable, rebuildable materialized face; DATA_MODEL §11 "可删后重建").
Rebuild consumes ONLY ACTIVE claims — a pending PRODUCED artifact is a
proposal, not evidence, and is never estimated (adjudicated: pending
PRODUCED = audit-only, P3+ re-visit). A claim set that violates the
BF-01 §7 EstimatorClaimView contract makes the rebuild fail loudly
(VALIDATION_FAILED) rather than silently computing corrupted canon. No
DecisionCycle is created (Phase 3+; decision_cycle_id stays nullable,
DEC-…eaaa5a1d.26 a).

Phase 3 P3-0 (TASK-…55 ①): ``get_learning_snapshot`` validates
projection/watermark consistency at read time — any §11 row whose
meta.evidence_watermark lags the durable watermark makes the read fail
CONFLICT instead of returning a stale view wearing the new watermark
(adjudicated disposition of DEC-…eaaa5a1d.48 F1; deterministic refusal,
no silent auto-rebuild).

Phase 4 P4-0 carryover (TASK-OPI-5ba74efc-….84 ①; DEC-…5ba74efc.68 C1):
the teaching evidence leg gained the durable-pending shape RA §21:616-621
asks for. ``commit_teaching_evidence`` now runs the chain

    Attempt durable → Evaluation durable → proposal PENDING durable
    (own short transaction) → commit attempt

and the three outcomes are all durable facts: COMMITTED (the commit
landed), REJECTED (Learning's validation refused it — the AnalysisArtifact
precedent of migration 0004), PENDING (the commit could not run: the
proposal waits, the attempt's evidence is not lost, and the turn keeps its
normal persona — RA §21 "durable proposal pending / normal persona / no
risky automatic remediation"). The retry face
(``retry_pending_teaching_evidence``) is explicit and host/recovery-driven;
it is deliberately NOT auto-wired in this slice. The table is Learning's
own (migration 0009) and is **not** a projection_job row: Learning
evidence is canonical input, not a rebuildable CP4 projection.

Default column values for claims committed through the Phase 0 protocol
face (``EvidenceGroupRecord`` / ``EvidenceClaimView`` carry fewer fields
than the DATA_MODEL §6 column set; the fill values below are
implementation-defined per DATA_MODEL §27 and reported):
- elicitation_type 'NATURAL' (word root shared with §7 opportunity_type;
  canonical pins no vocabulary)
- spontaneity 'SPONTANEOUS' (BF-01 §"v1.1 冻结": spontaneity ∈
  {INDEPENDENT, SPONTANEOUS})
- support_level ← claim.support; answer_exposure_state ← claim.exposure
- support_attribution_certainty 0.0 / basis 'UNSPECIFIED' (no canonical
  vocabulary yet)
- context/persona/modality novelty 0.0; optional quality columns as
  carried by the view

All SQL is a fixed literal with bound parameters — no identifier
assembly.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TypeVar, cast

from elc.conversation.types import CanonicalTurnSlice
from elc.learning.analysis import (
    ANALYSIS_TYPE_LEARNING_EVIDENCE,
    DETERMINISTIC_ANALYSIS_PRODUCER_ID,
    LearningEvidenceProposal,
    deterministic_evidence_commit_id,
    deterministic_evidence_group_id,
    produce_learning_evidence_proposal,
)
from elc.learning.estimator import (
    ESTIMATOR_PROFILE_ID,
    FRESHNESS_DAYS_AGING_MAX,
    FRESHNESS_DAYS_FRESH_MAX,
    EstimatorClaimView,
    EstimatorContractError,
    TargetStateEstimate,
    estimate_target_state,
)
from elc.learning.silent_claim import (
    SILENT_EVIDENCE_EVALUATOR_ID,
    SILENT_EVIDENCE_EVALUATOR_VERSION,
    SILENT_EVIDENCE_MODALITY,
    claim_for_silent_observation,
)
from elc.learning.target_match import (
    admitted_for_evidence,
    observe_target_match,
)
from elc.learning.target_resolution import (
    ResolvedTarget,
    resolution_from_document,
)
from elc.learning.teaching_evidence import (
    CAPABILITY_LINKAGE_CLAIM_ROLE,
    TeachingEvidenceSource,
    claims_for_teaching_evidence,
)
from elc.learning.types import (
    AttemptOutcome,
    ErrorAttribution,
    EvidenceClaimView,
    EvidenceGroupRecord,
    EvidenceModality,
    EvidencePolarity,
    EvidenceQualifier,
    EvidenceStatus,
    ExposureLevel,
    FreshnessView,
    LearnerCoverage,
    LearnerDimensionState,
    LearnerFreshness,
    LearnerProjection,
    LearnerTargetStateRecord,
    LearningSnapshot,
    PerformanceType,
    SupportLevel,
)
from elc.learning.validation import negative_evidence_refusal
from elc.platform.db.epoch import RuntimeEpochFence, StaleEpochError
from elc.platform.db.tx import short_transaction
from elc.platform.types import (
    AnalysisId,
    AttemptId,
    DomainError,
    DomainErrorCode,
    Err,
    EvaluatorVersion,
    EvidenceClaimId,
    EvidenceCommitId,
    EvidenceGroupId,
    LearningOpportunityId,
    LearningSnapshotId,
    MomentId,
    Ok,
    Result,
    TargetId,
    TurnId,
    UserTurnId,
)

__all__ = [
    "LOCAL_V1_DEFAULT_USER_SCOPE",
    "TEACHING_EVIDENCE_GROUP_PREFIX",
    "TEACHING_EVIDENCE_PROPOSAL_PREFIX",
    "TEACHING_EVIDENCE_PROPOSAL_STATUSES",
    "AnalysisArtifactRecord",
    "ClaimRecord",
    "GroupRecord",
    "SqliteLearningStore",
    "StaleStoreEpochError",
    "TeachingEvidenceProposalRecord",
    "teaching_evidence_group_id",
    "teaching_evidence_proposal_id",
]

T = TypeVar("T")

#: Local V1 single-user default scope key (adjudicated DEC-…eaaa5a1d.26 f):
#: the watermark and commit rows are keyed by a user scope; Local V1 has
#: exactly one user, so the store default is a single fixed scope.
LOCAL_V1_DEFAULT_USER_SCOPE = "user-local-v1"

#: The two deterministic id namespaces of one teaching attempt (P4-0 ①,
#: "双命名空间对账"): the durable *proposal* — Learning's pending commit
#: backlog, named ``tep-{attempt_id}`` and written by the teaching side into
#: §17 ``evidence_proposal_refs`` — and the *evidence group* the proposal
#: commits into, ``eg-teaching-{attempt_id}`` (the pre-P4-0 id, kept: a
#: committed group's identity does not change). Both derive from the attempt
#: id, so any re-entry re-derives the same physical keys; the teaching
#: package spells the proposal prefix itself (the AST pin forbids an import
#: in either direction) and tests/phase4 reconciles the two spellings.
TEACHING_EVIDENCE_PROPOSAL_PREFIX = "tep-"
TEACHING_EVIDENCE_GROUP_PREFIX = "eg-teaching-"

#: ``teaching_evidence_proposal.status`` vocabulary (migration 0009). The
#: same three-word shape the AnalysisArtifact precedent uses
#: (PRODUCED → COMMITTED / REJECTED), with PENDING naming the durable
#: pre-commit state RA §21 requires.
TEACHING_EVIDENCE_PROPOSAL_STATUSES = ("PENDING", "COMMITTED", "REJECTED")


def teaching_evidence_proposal_id(attempt_id: str) -> str:
    """The deterministic proposal id of one attempt (see the prefixes)."""
    return f"{TEACHING_EVIDENCE_PROPOSAL_PREFIX}{attempt_id}"


def teaching_evidence_group_id(attempt_id: str) -> str:
    """The deterministic evidence-group id of one attempt (see the
    prefixes): the committed group stays isomorphic to its proposal."""
    return f"{TEACHING_EVIDENCE_GROUP_PREFIX}{attempt_id}"

#: DATA_MODEL §6 claim outcome vocabulary is the four-value §6 list;
#: the Phase 0 protocol type reuses the STATE_MACHINES §5 five-value
#: attempt vocabulary, so ALTERNATIVE_SUCCESS is refused at the store
#: face (it is an attempt-evaluation word, not a §6 claim outcome).
_CLAIM_OUTCOME_VALUES = frozenset(
    {"SUCCESS", "PARTIAL", "FAILURE", "ABSTAIN"}
)


#: Column order of the evidence_claim SELECT literals (named row access
#: is built by zipping this list with the row tuple).
_CLAIM_COLUMNS: tuple[str, ...] = (
    "evidence_claim_id",
    "evidence_group_id",
    "opportunity_id",
    "target_type",
    "target_id",
    "performance_type",
    "polarity",
    "outcome",
    "qualifiers",
    "evidence_modality",
    "elicitation_type",
    "spontaneity",
    "support_level",
    "answer_exposure_state",
    "exposure_estimate_id",
    "support_attribution_certainty",
    "support_attribution_basis",
    "accuracy",
    "pragmatic_fit",
    "fluency",
    "error_attribution",
    "delay_seconds",
    "context_novelty",
    "persona_novelty",
    "evidence_modality_novelty",
    "capability_evidence_basis",
    "source_turn_id",
    "conversation_id",
    "persona_id",
    "teaching_moment_id",
    "evaluator_id",
    "evaluator_version",
    "evaluator_confidence",
    "status",
    "supersedes_claim_id",
    "attempt_id",
    "claim_role",
    "created_at",
)


#: Full-literal evidence_claim SELECT — the column-name whitelist as one
#: compile-time literal (identifiers are never assembled from runtime
#: values); shared by _claim_row / _claim_records_for /
#: get_evidence_group so the pinned column order has a single source.
_CLAIM_SELECT = (
    "SELECT evidence_claim_id, evidence_group_id, opportunity_id,"
    " target_type, target_id, performance_type, polarity, outcome,"
    " qualifiers, evidence_modality, elicitation_type, spontaneity,"
    " support_level, answer_exposure_state, exposure_estimate_id,"
    " support_attribution_certainty, support_attribution_basis,"
    " accuracy, pragmatic_fit, fluency, error_attribution, delay_seconds,"
    " context_novelty, persona_novelty, evidence_modality_novelty,"
    " capability_evidence_basis, source_turn_id, conversation_id,"
    " persona_id, teaching_moment_id, evaluator_id, evaluator_version,"
    " evaluator_confidence, status, supersedes_claim_id, attempt_id,"
    " claim_role, created_at FROM evidence_claim"
)


class StaleStoreEpochError(StaleEpochError):
    """A learning-store write was fenced by a newer runtime epoch."""


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _err(code: DomainErrorCode, message: str) -> Err[T]:
    return Err(DomainError(code=code, message=message))


@dataclass(frozen=True)
class AnalysisArtifactRecord:
    """Durable AnalysisArtifact row (DATA_MODEL §5; proposal-only)."""

    analysis_id: AnalysisId
    turn_id: TurnId
    analysis_type: str
    producer_id: str
    producer_version: str
    structured_proposal: str
    confidence: float
    status: str
    created_at: str


@dataclass(frozen=True)
class GroupRecord:
    """Durable EvidenceGroup row (DATA_MODEL §6)."""

    evidence_group_id: EvidenceGroupId
    source_turn_id: TurnId
    conversation_id: str
    persona_id: str | None
    teaching_moment_id: str | None
    evidence_modality: str
    created_at: str


@dataclass(frozen=True)
class ClaimRecord:
    """Durable EvidenceClaim row (DATA_MODEL §6 column set; plus the
    §25 commit-key columns attempt_id / claim_role)."""

    evidence_claim_id: EvidenceClaimId
    evidence_group_id: EvidenceGroupId
    opportunity_id: str | None
    target_type: str
    target_id: str
    performance_type: str
    polarity: str
    outcome: str
    qualifiers: tuple[str, ...]
    evidence_modality: str
    elicitation_type: str
    spontaneity: str
    support_level: str
    answer_exposure_state: str
    exposure_estimate_id: str | None
    support_attribution_certainty: float
    support_attribution_basis: str
    accuracy: float | None
    pragmatic_fit: float | None
    fluency: float | None
    error_attribution: str | None
    delay_seconds: int | None
    context_novelty: float
    persona_novelty: float
    evidence_modality_novelty: float
    capability_evidence_basis: str | None
    source_turn_id: TurnId
    conversation_id: str
    persona_id: str | None
    teaching_moment_id: str | None
    evaluator_id: str
    evaluator_version: str
    evaluator_confidence: float
    status: str
    supersedes_claim_id: EvidenceClaimId | None
    attempt_id: str | None
    claim_role: str | None
    created_at: str


@dataclass(frozen=True)
class TeachingEvidenceProposalRecord:
    """One durable ``teaching_evidence_proposal`` row (migration 0009).

    The provenance JSON column is decoded into its five named fields
    (``target_type`` / ``target_id`` / ``evaluator_id`` /
    ``evaluator_version`` / ``payload_hash``) so a caller never has to
    parse the document itself; ``payload`` stays the canonical JSON text
    (the claim views plus their commit context) because it is the exact
    bytes the commit is replayed from.
    """

    proposal_id: str
    source_attempt_id: str
    source_evaluation_id: str
    moment_id: str
    target_type: str
    target_id: str
    evaluator_id: str
    evaluator_version: str
    payload_hash: str
    payload: str
    status: str
    attempt_count: int
    created_at: str
    updated_at: str
    committed_at: str | None


class SqliteLearningStore:
    """Durable Learning evidence kernel: analysis artifacts, evidence
    groups/claims, CP1 commit unit + watermark, opportunities,
    self-reports, expression needs, supersede/invalidate."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        fence: RuntimeEpochFence,
        user_scope_id: str = LOCAL_V1_DEFAULT_USER_SCOPE,
    ) -> None:
        self._conn = conn
        self._fence = fence
        self._user_scope_id = user_scope_id

    # -- fencing -----------------------------------------------------------

    @property
    def current_epoch(self) -> int:
        return self._fence.current

    def _require_current_epoch(self) -> None:
        row = self._conn.execute("SELECT MAX(epoch) FROM runtime_epoch").fetchone()
        newest = None if row is None or row[0] is None else int(row[0])
        if newest is None or newest != self._fence.current:
            raise StaleStoreEpochError(
                f"learning store epoch={self._fence.current} fenced by"
                f" db epoch={newest}"
            )

    # -- LearningTurnAnalysis (RA §4 steps 3-4) ----------------------------

    def record_learning_analysis(
        self,
        turn: CanonicalTurnSlice,
        *,
        resolution: ResolvedTarget | None = None,
    ) -> Result[LearningEvidenceProposal]:
        """RA §4 step 3: deterministic producer → durable PRODUCED
        artifact. Idempotent: the (turn_id, analysis_type, producer_id)
        unique key replays the durable row (crash after CP0 re-enters
        analysis without double-producing, RA §23).

        P5-2: ``resolution`` is the chat leg's optional target observation
        (elc.learning.target_resolution), recorded as one more fact inside
        the proposal document — facts only, the §6 claim is Learning's
        conversion at commit time (elc.learning.silent_claim). A durable
        artifact that already exists is replayed as recorded, so a re-run
        can never swap the observed facts under a stable analysis id.
        """

        proposal = produce_learning_evidence_proposal(
            turn, resolution=resolution
        )
        try:
            with short_transaction(self._conn):
                self._require_current_epoch()
                existing = self._artifact_row_for(
                    turn.turn_id,
                    ANALYSIS_TYPE_LEARNING_EVIDENCE,
                    DETERMINISTIC_ANALYSIS_PRODUCER_ID,
                )
                if existing is not None:
                    return Ok(self._proposal_from_row(existing))
                self._conn.execute(
                    "INSERT INTO analysis_artifact ("
                    " analysis_id, turn_id, analysis_type, producer_id,"
                    " producer_version, structured_proposal, confidence,"
                    " status, created_at"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, 'PRODUCED', ?)",
                    (
                        proposal.analysis_id,
                        turn.turn_id,
                        ANALYSIS_TYPE_LEARNING_EVIDENCE,
                        proposal.producer_id,
                        proposal.producer_version,
                        proposal.structured_proposal,
                        proposal.confidence,
                        _now(),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            return _err(DomainErrorCode.CONFLICT, str(exc))
        return Ok(proposal)

    def commit_learning_evidence(
        self,
        proposal: LearningEvidenceProposal,
        turn: CanonicalTurnSlice,
        persona_id: str | None = None,
    ) -> Result[EvidenceCommitId]:
        """RA §4 step 4 / CP1 (RUNTIME §6): validate the proposal →
        commit the EvidenceGroup → advance the durable watermark → mark
        the artifact COMMITTED. One short transaction; replay after
        "crash after CP1" returns the original EvidenceCommitId without
        writing (RA §22/§23).

        Learning decides (DOMAIN_MODEL §18): an unobservable proposal is
        REJECTED (the artifact flip rides the same transaction); a
        proposal whose utterance no longer matches the canonical turn is
        a validation failure (proposal/turn binding).

        P5-2: a proposal whose durable document carries a target
        observation commits that observation's §6 claim into the same
        group — one observable behavior, one group (DATA_MODEL §6), which
        is also what the group's (turn, modality) unique key requires. The
        claim is built from the durable document and validated through the
        ordinary claim face (``_claim_refusal``: ACTIVE, vocabularies,
        the §6 negative-evidence gate) before anything is written; a
        refused claim flips the artifact REJECTED like any other refusal.
        """

        try:
            with short_transaction(self._conn):
                self._require_current_epoch()
                artifact = self._artifact_row(proposal.analysis_id)
                if artifact is None:
                    return _err(
                        DomainErrorCode.NOT_FOUND,
                        f"analysis artifact not found: {proposal.analysis_id}"
                        " (record_learning_analysis must run first)",
                    )
                status = str(artifact[7])
                # The handed-in proposal must be the durable one: a
                # caller cannot swap content under a stable analysis_id.
                if (
                    proposal.turn_id != str(artifact[1])
                    or proposal.producer_id != str(artifact[3])
                    or proposal.producer_version != str(artifact[4])
                    or proposal.structured_proposal != str(artifact[5])
                ):
                    return _err(
                        DomainErrorCode.CONFLICT,
                        "proposal does not match the durable artifact for"
                        f" {proposal.analysis_id} — content under a stable"
                        " analysis_id is immutable",
                    )
                if status == "COMMITTED":
                    replay = self._commit_row_by_analysis(proposal.analysis_id)
                    if replay is not None:
                        return Ok(EvidenceCommitId(str(replay[0])))
                    return _err(
                        DomainErrorCode.CONFLICT,
                        "artifact is COMMITTED but has no evidence commit",
                    )
                if status != "PRODUCED":
                    return _err(
                        DomainErrorCode.CONFLICT,
                        "artifact status"
                        f" {status} cannot enter CP1 (expect PRODUCED)",
                    )

                parsed = _parse_proposal(artifact[5])
                refusal = _proposal_refusal(parsed, turn)
                if refusal is not None:
                    self._conn.execute(
                        "UPDATE analysis_artifact SET status = 'REJECTED'"
                        " WHERE analysis_id = ?",
                        (proposal.analysis_id,),
                    )
                    return Err(refusal)
                # P5-2: a proposal that carries a target observation commits
                # its own §6 claim with the group (one observable behavior,
                # one group — DATA_MODEL §6). The claim is built from the
                # DURABLE document, never from the handed-in proposal, so the
                # recorded facts are the facts that landed.
                claim, claim_refusal = _silent_claim_for_proposal(parsed, turn)
                if claim_refusal is not None:
                    self._conn.execute(
                        "UPDATE analysis_artifact SET status = 'REJECTED'"
                        " WHERE analysis_id = ?",
                        (proposal.analysis_id,),
                    )
                    return Err(claim_refusal)
                if claim is not None:
                    claim_target = TargetId(str(claim.target_id))
                    refusal = self._claim_refusal(claim, claim_target)
                    if refusal is not None:
                        self._conn.execute(
                            "UPDATE analysis_artifact SET status = 'REJECTED'"
                            " WHERE analysis_id = ?",
                            (proposal.analysis_id,),
                        )
                        return Err(refusal)

                modality = str(parsed["evidence_modality"])
                group_id = deterministic_evidence_group_id(
                    turn.turn_id, modality
                )
                existing_commit = self._commit_row_by_group(group_id)
                if existing_commit is not None:
                    # The group already committed under this artifact's
                    # key space: flip the artifact and replay the commit.
                    self._conn.execute(
                        "UPDATE analysis_artifact SET status = 'COMMITTED'"
                        " WHERE analysis_id = ?",
                        (proposal.analysis_id,),
                    )
                    return Ok(EvidenceCommitId(str(existing_commit[0])))

                self._conn.execute(
                    "INSERT INTO evidence_group ("
                    " evidence_group_id, source_turn_id, conversation_id,"
                    " persona_id, teaching_moment_id, evidence_modality,"
                    " created_at"
                    ") VALUES (?, ?, ?, ?, NULL, ?, ?)",
                    (
                        group_id,
                        turn.turn_id,
                        turn.conversation_id,
                        persona_id,
                        modality,
                        _now(),
                    ),
                )
                if claim is not None:
                    # The silent observation's own claim (P5-2). The group
                    # record mirrors the row just inserted: no moment, no
                    # attempt, the silent evaluator identity; the claim id is
                    # the view's deterministic id (ecl-silent-{turn}).
                    self._insert_claim(
                        claim=claim,
                        group=EvidenceGroupRecord(
                            evidence_group_id=group_id,
                            moment_id=None,
                            attempt_id=None,
                            target_id=TargetId(str(claim.target_id)),
                            evaluator_version=EvaluatorVersion(
                                SILENT_EVIDENCE_EVALUATOR_VERSION
                            ),
                            claims=(claim,),
                        ),
                        source_turn_id=turn.turn_id,
                        conversation_id=turn.conversation_id,
                        persona_id=persona_id,
                        evaluator_id=SILENT_EVIDENCE_EVALUATOR_ID,
                        supersedes_claim_id=None,
                        claim_id=EvidenceClaimId(str(claim.evidence_claim_id)),
                    )
                watermark = self._bump_watermark()
                commit_id = EvidenceCommitId(
                    deterministic_evidence_commit_id(group_id)
                )
                self._conn.execute(
                    "INSERT INTO evidence_commit ("
                    " evidence_commit_id, evidence_group_id, analysis_id,"
                    " user_scope_id, watermark_after, committed_at"
                    ") VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        commit_id,
                        group_id,
                        proposal.analysis_id,
                        self._user_scope_id,
                        watermark,
                        _now(),
                    ),
                )
                self._conn.execute(
                    "UPDATE analysis_artifact SET status = 'COMMITTED'"
                    " WHERE analysis_id = ?",
                    (proposal.analysis_id,),
                )
                return Ok(commit_id)
        except sqlite3.IntegrityError as exc:
            return _err(DomainErrorCode.CONFLICT, str(exc))

    # -- LearningCommands (Phase 0 protocol face) ---------------------------

    def commit_evidence_group(
        self,
        group: EvidenceGroupRecord,
        *,
        source_turn_id: TurnId | None = None,
        conversation_id: str | None = None,
        persona_id: str | None = None,
        evaluator_id: str = "learning-store-v1",
    ) -> Result[EvidenceCommitId]:
        """CP1 via the Phase 0 protocol face: validate every claim
        ( Learning decides, DOMAIN_MODEL §6/§18 — including the
        negative-evidence rule) → insert group + claims (ACTIVE) →
        advance the watermark → record the commit. One short transaction.

        Idempotent on the group: a replayed group returns the original
        EvidenceCommitId without writing (§25 commit identity; RA §23).
        ``source_turn_id`` / ``conversation_id`` are required by the §6
        column set (the Phase 0 record type carries neither); they are
        keyword-only additions so the frozen protocol signature stays
        callable.
        """

        if source_turn_id is None or conversation_id is None:
            return _err(
                DomainErrorCode.VALIDATION_FAILED,
                "source_turn_id and conversation_id are required by the"
                " DATA_MODEL §6 EvidenceGroup column set (Phase 0 protocol"
                " record carries neither; pass them as keyword arguments)",
            )
        try:
            with short_transaction(self._conn):
                self._require_current_epoch()
                replay = self._commit_row_by_group(group.evidence_group_id)
                if replay is not None:
                    return Ok(EvidenceCommitId(str(replay[0])))

                # Validate every claim BEFORE any write: a refused claim
                # leaves the unit empty (the Err return commits an empty
                # transaction — no residue; the P1 store precedent).
                for claim in group.claims:
                    refusal = self._claim_refusal(
                        claim, group.target_id, group
                    )
                    if refusal is not None:
                        return Err(refusal)

                existing_group = self._group_row(group.evidence_group_id)
                if existing_group is None:
                    self._conn.execute(
                        "INSERT INTO evidence_group ("
                        " evidence_group_id, source_turn_id,"
                        " conversation_id, persona_id, teaching_moment_id,"
                        " evidence_modality, created_at"
                        ") VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            group.evidence_group_id,
                            source_turn_id,
                            conversation_id,
                            persona_id,
                            group.moment_id,
                            _group_modality(group),
                            _now(),
                        ),
                    )
                else:
                    if (
                        str(existing_group[1]) != source_turn_id
                        or str(existing_group[2]) != conversation_id
                    ):
                        return _err(
                            DomainErrorCode.CONFLICT,
                            "group id already durable with different"
                            " provenance",
                        )

                for claim in group.claims:
                    self._insert_claim(
                        claim=claim,
                        group=group,
                        source_turn_id=source_turn_id,
                        conversation_id=conversation_id,
                        persona_id=persona_id,
                        evaluator_id=evaluator_id,
                        supersedes_claim_id=None,
                    )

                watermark = self._bump_watermark()
                commit_id = EvidenceCommitId(
                    deterministic_evidence_commit_id(group.evidence_group_id)
                )
                self._conn.execute(
                    "INSERT INTO evidence_commit ("
                    " evidence_commit_id, evidence_group_id, analysis_id,"
                    " user_scope_id, watermark_after, committed_at"
                    ") VALUES (?, ?, NULL, ?, ?, ?)",
                    (
                        commit_id,
                        group.evidence_group_id,
                        self._user_scope_id,
                        watermark,
                        _now(),
                    ),
                )
                return Ok(commit_id)
        except sqlite3.IntegrityError as exc:
            return _err(DomainErrorCode.CONFLICT, str(exc))

    def record_self_report(
        self,
        user_id: str,
        target_id: TargetId,
        claim: str,
        *,
        user_turn_id: UserTurnId | None = None,
        target_type: str = "RESOURCE",
        scope: str | None = None,
    ) -> Result[EvidenceGroupId]:
        """Durable LearnerSelfReport (DATA_MODEL §8 "不直接改 Ability").

        A self report never enters the evidence kernel: no
        EvidenceGroup/EvidenceClaim row is written and the watermark does
        not move (BF-01 / TASK-…30 ⑥). The Phase 0 protocol return type
        reuses ``EvidenceGroupId`` as the opaque durable handle — the
        returned value wraps the durable self_report_id (a self report is
        deliberately NOT an evidence group; signature frozen in Phase 0).

        ``claim`` must be one of the §8 report_type words. ``user_id``
        has no §8 column (Local V1 single user) and is deliberately not
        persisted — the conversation-store user_id precedent.
        ``user_turn_id`` is required by the §8 column set.
        """

        del user_id  # DATA_MODEL §8 LearnerSelfReport has no user_id column.
        if user_turn_id is None:
            return _err(
                DomainErrorCode.VALIDATION_FAILED,
                "user_turn_id is required by the DATA_MODEL §8"
                " LearnerSelfReport column set",
            )
        report_types = {
            "CLAIMS_KNOWN",
            "CLAIMS_UNKNOWN",
            "TYPO_DECLARED",
            "TOO_EASY",
            "TOO_HARD",
        }
        if claim not in report_types:
            return _err(
                DomainErrorCode.VALIDATION_FAILED,
                f"claim={claim!r} is not a DATA_MODEL §8 report_type word",
            )
        self_report_id = f"sr-{uuid.uuid4().hex}"
        try:
            with short_transaction(self._conn):
                self._require_current_epoch()
                self._conn.execute(
                    "INSERT INTO learner_self_report ("
                    " self_report_id, user_turn_id, target_type,"
                    " target_id, report_type, scope, created_at"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        self_report_id,
                        user_turn_id,
                        target_type,
                        target_id,
                        claim,
                        scope,
                        _now(),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            return _err(DomainErrorCode.CONFLICT, str(exc))
        return Ok(EvidenceGroupId(self_report_id))

    def rebuild_learner_state(
        self,
        target_id: TargetId,
        evidence_modality: str,
    ) -> Result[str]:
        """P2B (TASK-…44): recompute the materialized LearnerTargetState
        projection (DATA_MODEL §11) for one target_id × evidence_modality
        from the ACTIVE canonical claims, for every target_type that
        target's claims span. One short transaction: estimate all scopes
        first, then replace the stored rows — a refusal leaves the
        previous projection intact.

        The rebuild consumes ONLY ACTIVE claims (BF-01 §29): a pending
        PRODUCED artifact is a proposal and is never estimated. The
        projection is stamped with the durable evidence watermark and the
        rebuild wall clock (freshness is evaluated at rebuild time; time
        never changes historical ability mass, BF-01 §22). Committed
        claims violating the BF-01 §7 contract fail loudly
        (VALIDATION_FAILED) instead of being silently computed. Signature
        frozen (Phase 0 protocol; the returned str is the opaque
        StateVersion of this rebuild)."""

        try:
            with short_transaction(self._conn):
                self._require_current_epoch()
                type_rows = self._conn.execute(
                    "SELECT DISTINCT target_type FROM evidence_claim"
                    " WHERE target_id = ? AND evidence_modality = ?"
                    " ORDER BY target_type",
                    (target_id, evidence_modality),
                ).fetchall()
                watermark = self.get_evidence_watermark()
                as_of = _now()
                documents: list[tuple[str, str]] = []
                for row in type_rows:
                    target_type = str(row[0])
                    claims = self._claim_records_for(
                        target_type, target_id, evidence_modality
                    )
                    views = [_estimator_view(claim) for claim in claims]
                    try:
                        estimate = estimate_target_state(
                            views,
                            target_type=target_type,
                            target_id=str(target_id),
                            modality=evidence_modality,
                            as_of=as_of,
                        )
                    except EstimatorContractError as exc:
                        return _err(
                            DomainErrorCode.VALIDATION_FAILED,
                            "BF-01 §7 contract violation among committed"
                            f" claims for {target_type}/{target_id}/"
                            f"{evidence_modality}: {exc}",
                        )
                    record = _record_from_estimate(
                        estimate, watermark, as_of
                    )
                    documents.append(
                        (target_type, _state_document(record))
                    )
                self._conn.execute(
                    "DELETE FROM learner_target_state"
                    " WHERE user_scope_id = ? AND target_id = ?"
                    " AND evidence_modality = ?",
                    (self._user_scope_id, target_id, evidence_modality),
                )
                for target_type, document in documents:
                    self._conn.execute(
                        "INSERT INTO learner_target_state ("
                        " user_scope_id, target_type, target_id,"
                        " evidence_modality, estimator_version,"
                        " evidence_watermark, state_json, updated_at"
                        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            self._user_scope_id,
                            target_type,
                            target_id,
                            evidence_modality,
                            ESTIMATOR_PROFILE_ID,
                            watermark,
                            document,
                            as_of,
                        ),
                    )
                version = "sv-" + _stable_digest(
                    self._user_scope_id,
                    str(target_id),
                    evidence_modality,
                    str(watermark),
                    as_of,
                )[:24]
                return Ok(version)
        except sqlite3.IntegrityError as exc:
            return _err(DomainErrorCode.CONFLICT, str(exc))

    # -- LearningQueries (P2B; signatures frozen) ---------------------------

    def get_learner_target_state(
        self, target_id: TargetId, evidence_modality: str
    ) -> Result[LearnerTargetStateRecord | None]:
        """Read the materialized §11 projection row for one target_id ×
        modality. Ok(None) when the scope was never rebuilt.

        Scope note (P3-0 review F5, DEC-…eaaa5a1d.58): this single-row
        read is deliberately NOT subject to the snapshot read-time
        watermark gate. The gate exists so a *snapshot* never claims
        watermark=N+1 while riding targets computed at <=N; a single row
        reports its own stored stamp (which the caller can compare), and
        the P3-0 test pins that it stays readable while the snapshot
        refuses. Reading one row is not materializing the projection
        view."""

        rows = self._conn.execute(
            "SELECT state_json FROM learner_target_state"
            " WHERE user_scope_id = ? AND target_id = ?"
            " AND evidence_modality = ? ORDER BY target_type",
            (self._user_scope_id, target_id, evidence_modality),
        ).fetchall()
        if not rows:
            return Ok(None)
        if len(rows) > 1:
            return _err(
                DomainErrorCode.CONFLICT,
                "target_id spans multiple target_types in the §11"
                " projection scope; the frozen Phase 0 query face carries"
                " no target_type — read the LearningSnapshot for the"
                " full per-type view",
            )
        document: dict[str, object] = json.loads(str(rows[0][0]))
        return Ok(_record_from_document(document))

    def get_learning_snapshot(
        self, learning_snapshot_id: str | None = None
    ) -> Result[LearningSnapshot]:
        """Materialize the §12 LearningSnapshot: every LearnerTargetState
        of the store's user scope + the durable watermark + estimator
        version. Evidence-derived ONLY (§12 red line: goal importance /
        review due / teaching priority / exam importance are structurally
        absent — pinned by test).

        Read-time watermark consistency (P3-0, TASK-…55 ① / DEC-…48 F1
        adjudication): every target row's §11 meta.evidence_watermark must
        equal the current durable watermark. A commit / supersede /
        invalidate that advanced the sequence (F2) without a rebuild left
        the projection stale, and this read deterministically REFUSES
        (CONFLICT) — it never materializes a snapshot whose top-level
        watermark=N+1 rides targets computed at <=N (the review
        counterexample). Refusal over silent masking by design: no
        auto-rebuild fires here; the caller runs ``rebuild_learner_state``
        for the affected targets and re-reads (rebuild stamps the current
        watermark, so the refusal clears).

        ``learning_snapshot_id`` (frozen Phase 0 parameter): Local V1
        keeps no snapshot archive — the snapshot is a view over the
        current projection — so the id is derived deterministically from
        (estimator version, watermark, target keys) and passing any other
        id is NOT_FOUND (implementation-defined narrowing, DATA_MODEL
        §27). ``as_of`` is the read wall clock. An empty projection
        (no §11 rows) has nothing to be stale and reads Ok with zero
        targets."""

        rows = self._projection_rows()
        watermark = self.get_evidence_watermark()
        targets = tuple(
            _record_from_document(json.loads(str(row[3])))
            for row in rows
        )
        stale = [
            record
            for record in targets
            if record.evidence_watermark != watermark
        ]
        if stale:
            example = stale[0]
            return _err(
                DomainErrorCode.CONFLICT,
                "stale LearnerTargetState projection: "
                f"{example.target_type}/{example.target_id}/"
                f"{example.evidence_modality} carries"
                f" evidence_watermark={example.evidence_watermark} but"
                f" the durable watermark is {watermark} —"
                " rebuild_learner_state must run before the snapshot is"
                " read (read-time refusal, no silent auto-rebuild;"
                " DEC-…eaaa5a1d.48 F1)",
            )
        keys = [
            f"{row[0]}\x1f{row[1]}\x1f{row[2]}" for row in rows
        ]
        snapshot_id = LearningSnapshotId(
            "lsnap-"
            + _stable_digest(
                ESTIMATOR_PROFILE_ID, str(watermark), *keys
            )[:24]
        )
        if learning_snapshot_id is not None and learning_snapshot_id != snapshot_id:
            return _err(
                DomainErrorCode.NOT_FOUND,
                f"learning snapshot {learning_snapshot_id} not found —"
                " Local V1 materializes only the current projection"
                f" snapshot ({snapshot_id})",
            )
        estimator_version = (
            targets[0].estimator_version if targets else ESTIMATOR_PROFILE_ID
        )
        return Ok(
            LearningSnapshot(
                learning_snapshot_id=snapshot_id,
                user_scope_id=self._user_scope_id,
                as_of=_now(),
                estimator_version=estimator_version,
                evidence_watermark=watermark,
                targets=targets,
            )
        )

    def stale_projection_targets(
        self,
    ) -> Result[tuple[tuple[TargetId, str], ...]]:
        """The §11 rows whose meta.evidence_watermark lags the durable
        watermark — exactly the set ``get_learning_snapshot`` refuses on,
        in the same deterministic order (target_type, target_id,
        evidence_modality) and computed by the same staleness rule.

        This is the repair face the caller needs when a snapshot read
        returns the CONFLICT above (P3-1A keep-snapshot-consistent
        coordination): rebuild every returned (target_id, modality) with
        ``rebuild_learner_state`` and re-read. The read itself never
        auto-rebuilds (the P3-0 adjudication: refusal over silent
        masking); it only names what must be rebuilt.

        Adjudicated name/vocabulary: the frozen Phase 0 query face has no
        such method, so this is an explicit Phase 3 extension (F1's
        scope-declaration lesson) — no protocol changes."""

        watermark = self.get_evidence_watermark()
        stale: list[tuple[TargetId, str]] = []
        for row in self._projection_rows():
            record = _record_from_document(json.loads(str(row[3])))
            if record.evidence_watermark != watermark:
                stale.append((TargetId(str(row[1])), str(row[2])))
        return Ok(tuple(stale))

    def get_freshness(self, target_id: TargetId) -> Result[FreshnessView]:
        """The only thing Learning owes the Scheduler (D-INV-009):
        freshness across the target's modality projections — the newest
        strong retrieval wins, elapsed is recomputed at read time (BF-01
        §22: time never changes historical ability mass)."""
        rows = self._conn.execute(
            "SELECT state_json FROM learner_target_state"
            " WHERE user_scope_id = ? AND target_id = ?"
            " ORDER BY updated_at, target_type, evidence_modality",
            (self._user_scope_id, target_id),
        ).fetchall()
        if not rows:
            return Ok(
                FreshnessView(
                    target_id=target_id,
                    last_strong_retrieval_at=None,
                    days_since_strong_retrieval=None,
                    freshness_band="UNKNOWN",
                    stability_band=None,
                )
            )
        records = [
            _record_from_document(json.loads(str(row[0]))) for row in rows
        ]
        with_strong = [
            record
            for record in records
            if record.freshness.last_strong_retrieval_at is not None
        ]
        as_of = datetime.now(tz=UTC)
        if with_strong:
            newest = max(
                with_strong,
                key=lambda record: (
                    record.freshness.last_strong_retrieval_at or "",
                    record.updated_at,
                ),
            )
            last = datetime.fromisoformat(
                str(newest.freshness.last_strong_retrieval_at)
            )
            days = max(0.0, (as_of - last).total_seconds() / 86400)
            if days <= FRESHNESS_DAYS_FRESH_MAX:
                band = "FRESH"
            elif days <= FRESHNESS_DAYS_AGING_MAX:
                band = "AGING"
            else:
                band = "STALE"
            return Ok(
                FreshnessView(
                    target_id=target_id,
                    last_strong_retrieval_at=newest.freshness.last_strong_retrieval_at,
                    days_since_strong_retrieval=round(days, 2),
                    freshness_band=band,
                    stability_band=newest.projection.stability_band,
                )
            )
        newest = max(records, key=lambda record: record.updated_at)
        return Ok(
            FreshnessView(
                target_id=target_id,
                last_strong_retrieval_at=None,
                days_since_strong_retrieval=None,
                freshness_band="UNKNOWN",
                stability_band=newest.projection.stability_band,
            )
        )

    # -- teaching evidence (P3-1B) ------------------------------------------

    def commit_teaching_evidence(
        self,
        proposal: TeachingEvidenceSource,
        *,
        source_turn_id: TurnId,
        conversation_id: str,
        source_evaluation_id: str,
        persona_id: str | None = None,
    ) -> Result[EvidenceCommitId]:
        """CP1 for one teaching attempt, in the RA §21 durable-pending shape
        (P4-0 ①; DEC-…5ba74efc.68 C1).

        Two short transactions, in this order and for this reason:

        1. ``record_teaching_evidence_proposal`` — the proposal becomes
           durable PENDING *before* the commit is attempted, so a crash or
           an unavailable Learning store can no longer swallow it (RA §21
           "durable proposal pending": the Attempt/Evaluation/refs are
           already durable, and now so is the evidence they produced);
        2. ``commit_teaching_evidence_proposal`` — the commit itself. On
           success the row flips COMMITTED; on Learning's validation
           refusal it flips REJECTED; on anything else it stays PENDING with
           the attempt counted, and the caller's teaching turn continues
           with its normal persona (never blocked by this leg).

        The group is deterministic on the attempt (``eg-teaching-{attempt}``
        and §25's ``moment_id + attempt_id + target_id + claim_role +
        evaluator_version`` commit key), so a re-entry — or a retry of the
        durable proposal — replays the durable commit instead of
        double-writing.

        A conversion refusal (an unknown vocabulary word in the teaching
        facts) still returns Learning's REJECT decision with nothing
        written: there is no valid proposal to persist, and the evaluation
        row's ref — a forward reference by construction — simply has no
        proposal to point at (the pre-P4-0 semantics, preserved).
        """

        recorded = self.record_teaching_evidence_proposal(
            proposal,
            source_evaluation_id=source_evaluation_id,
            source_turn_id=source_turn_id,
            conversation_id=conversation_id,
            persona_id=persona_id,
        )
        if isinstance(recorded, Err):
            return recorded
        return self.commit_teaching_evidence_proposal(recorded.value.proposal_id)

    def record_teaching_evidence_proposal(
        self,
        proposal: TeachingEvidenceSource,
        *,
        source_evaluation_id: str,
        source_turn_id: TurnId,
        conversation_id: str,
        persona_id: str | None = None,
    ) -> Result[TeachingEvidenceProposalRecord]:
        """Step 1 of the RA §21 chain: one durable PENDING proposal row, in
        its own short transaction (migration 0009).

        The payload is Learning's own conversion of the teaching facts
        (``claims_for_teaching_evidence`` — the §5 capability-positive /
        resource-neutral fold included) plus the commit context the later
        commit needs (group id, source turn, conversation, persona), so the
        durable row is self-contained: a retry after the process died needs
        no live teaching object and no cross-domain read.

        Idempotent on the deterministic proposal id (``tep-{attempt_id}``):
        a re-entry that re-derives the same payload replays the durable row
        and writes nothing; a *different* payload under a stable proposal id
        is refused (CONFLICT) — content under a stable id is immutable, the
        ``commit_learning_evidence`` precedent.
        """

        claims = claims_for_teaching_evidence(proposal)
        if isinstance(claims, Err):
            return claims
        proposal_id = teaching_evidence_proposal_id(proposal.attempt_id)
        payload = _teaching_evidence_payload(
            attempt_id=proposal.attempt_id,
            claims=claims.value,
            evaluator_id=proposal.evaluator_id,
            evaluator_version=proposal.evaluator_version,
            target_id=proposal.target_id,
            source_turn_id=source_turn_id,
            conversation_id=conversation_id,
            persona_id=persona_id,
        )
        provenance = json.dumps(
            {
                "target_type": proposal.target_type,
                "target_id": proposal.target_id,
                "evaluator_id": proposal.evaluator_id,
                "evaluator_version": proposal.evaluator_version,
                "payload_hash": hashlib.sha256(
                    payload.encode("utf-8")
                ).hexdigest(),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        try:
            with short_transaction(self._conn):
                self._require_current_epoch()
                existing = self._proposal_row(proposal_id)
                if existing is not None:
                    if str(existing[5]) != payload:
                        return _err(
                            DomainErrorCode.CONFLICT,
                            f"proposal {proposal_id} is already durable with"
                            " a different payload — content under a stable"
                            " proposal id is immutable",
                        )
                    return Ok(self._proposal_record(existing))
                now = _now()
                self._conn.execute(
                    "INSERT INTO teaching_evidence_proposal ("
                    " proposal_id, source_attempt_id, source_evaluation_id,"
                    " moment_id, provenance, payload, status, attempt_count,"
                    " created_at, updated_at, committed_at"
                    ") VALUES (?, ?, ?, ?, ?, ?, 'PENDING', 0, ?, ?, NULL)",
                    (
                        proposal_id,
                        proposal.attempt_id,
                        source_evaluation_id,
                        proposal.moment_id,
                        provenance,
                        payload,
                        now,
                        now,
                    ),
                )
                recorded = self._proposal_row(proposal_id)
                assert recorded is not None  # the insert above
                return Ok(self._proposal_record(recorded))
        except sqlite3.IntegrityError as exc:
            # e.g. an unknown attempt / evaluation / moment id (the FKs).
            return _err(DomainErrorCode.CONFLICT, str(exc))

    def commit_teaching_evidence_proposal(
        self, proposal_id: str
    ) -> Result[EvidenceCommitId]:
        """Step 2 of the RA §21 chain: commit one proposal from its durable
        payload — idempotently.

        - PENDING: the payload is parsed back into claims and committed
          through the same kernel as any other evidence
          (``commit_evidence_group``: validation → group + claims →
          watermark). Learning's *validation* refusal (VALIDATION_FAILED:
          vocabulary, the §6 negative-evidence rule, the LOR association)
          flips the row REJECTED — a deterministic verdict is durable, not
          retried forever. Any other failure (CONFLICT / a sqlite error, an
          unavailable dependency) leaves the row PENDING with the attempt
          counted: RA §21 "no risky automatic remediation".
        - COMMITTED: idempotent replay — the durable EvidenceCommitId comes
          back and nothing is written. A second commit attempt can therefore
          never double-count evidence or move the watermark twice.
        - REJECTED: refused; a rejected proposal is never re-committed
          (a new attempt is a new attempt — DOMAIN_MODEL §18).
        """

        row = self._proposal_row(proposal_id)
        if row is None:
            return _err(
                DomainErrorCode.NOT_FOUND,
                f"teaching evidence proposal not found: {proposal_id}",
            )
        status = str(row[6])
        context = _teaching_evidence_commit_context(row)
        if status == "COMMITTED":
            replay = self._commit_row_by_group(
                EvidenceGroupId(context.evidence_group_id)
            )
            if replay is None:
                return _err(
                    DomainErrorCode.CONFLICT,
                    f"proposal {proposal_id} is COMMITTED but has no"
                    " evidence commit",
                )
            return Ok(EvidenceCommitId(str(replay[0])))
        if status == "REJECTED":
            return _err(
                DomainErrorCode.CONFLICT,
                f"proposal {proposal_id} was REJECTED by Learning; a"
                " rejected proposal is never re-committed (DOMAIN_MODEL"
                " §18)",
            )

        committed = self.commit_evidence_group(
            _teaching_evidence_group(row, context),
            source_turn_id=TurnId(context.source_turn_id),
            conversation_id=context.conversation_id,
            persona_id=context.persona_id,
            evaluator_id=context.evaluator_id,
        )
        if isinstance(committed, Ok):
            self._settle_proposal(proposal_id, "COMMITTED")
            return committed
        if committed.error.code is DomainErrorCode.VALIDATION_FAILED:
            self._settle_proposal(proposal_id, "REJECTED")
        else:
            self._settle_proposal(proposal_id, "PENDING")
        return committed

    def retry_pending_teaching_evidence(
        self,
    ) -> Result[tuple[tuple[str, EvidenceCommitId], ...]]:
        """The explicit retry face (RA §21: pending proposals are retried
        deliberately, never by a background loop — "no risky automatic
        remediation", and Local V1 has no TTL/heartbeat scheduler).

        Walks the durable PENDING backlog in (created_at, proposal_id)
        order and attempts each commit through
        ``commit_teaching_evidence_proposal``. Idempotent: a proposal that
        already committed is no longer PENDING and is not revisited; a
        proposal that still cannot commit stays PENDING (or flips REJECTED)
        and is reported by its own durable row rather than by an exception.

        Returns the ``(proposal_id, evidence_commit_id)`` pairs this call
        committed; the deferred remainder is readable through
        ``get_teaching_evidence_proposal``. Not auto-wired in P4-0: the
        caller is the host / the later recovery line.
        """

        rows = self._conn.execute(
            "SELECT proposal_id FROM teaching_evidence_proposal"
            " WHERE status = 'PENDING' ORDER BY created_at, proposal_id"
        ).fetchall()
        committed: list[tuple[str, EvidenceCommitId]] = []
        for row in rows:
            proposal_id = str(row[0])
            outcome = self.commit_teaching_evidence_proposal(proposal_id)
            if isinstance(outcome, Ok):
                committed.append((proposal_id, outcome.value))
        return Ok(tuple(committed))

    def get_teaching_evidence_proposal(
        self, proposal_id: str
    ) -> Result[TeachingEvidenceProposalRecord | None]:
        """Read one durable proposal row (None = never recorded)."""

        row = self._proposal_row(proposal_id)
        return Ok(None if row is None else self._proposal_record(row))

    def _settle_proposal(self, proposal_id: str, status: str) -> None:
        """Count one commit attempt and record its verdict, in one short
        transaction — only while the row is still PENDING, so a lost race
        never rewrites another writer's verdict. COMMITTED stamps
        ``committed_at``; PENDING deliberately leaves it NULL (that is what
        makes "pending" auditable rather than inferred)."""

        with short_transaction(self._conn):
            self._require_current_epoch()
            now = _now()
            self._conn.execute(
                "UPDATE teaching_evidence_proposal SET status = ?,"
                " attempt_count = attempt_count + 1, updated_at = ?,"
                " committed_at = CASE WHEN ? = 'COMMITTED' THEN ?"
                " ELSE committed_at END"
                " WHERE proposal_id = ? AND status = 'PENDING'",
                (status, now, status, now, proposal_id),
            )

    def _proposal_row(self, proposal_id: str) -> Sequence[object] | None:
        """The proposal row as a positional tuple (the store's rows are
        tuples — no row_factory), column order pinned by the SELECT below."""

        return self._conn.execute(
            "SELECT proposal_id, source_attempt_id, source_evaluation_id,"
            " moment_id, provenance, payload, status, attempt_count,"
            " created_at, updated_at, committed_at"
            " FROM teaching_evidence_proposal WHERE proposal_id = ?",
            (proposal_id,),
        ).fetchone()

    @staticmethod
    def _proposal_record(row: Sequence[object]) -> TeachingEvidenceProposalRecord:
        provenance: dict[str, object] = json.loads(str(row[4]))
        return TeachingEvidenceProposalRecord(
            proposal_id=str(row[0]),
            source_attempt_id=str(row[1]),
            source_evaluation_id=str(row[2]),
            moment_id=str(row[3]),
            target_type=str(provenance["target_type"]),
            target_id=str(provenance["target_id"]),
            evaluator_id=str(provenance["evaluator_id"]),
            evaluator_version=str(provenance["evaluator_version"]),
            payload_hash=str(provenance["payload_hash"]),
            payload=str(row[5]),
            status=str(row[6]),
            attempt_count=int(cast(int, row[7])),
            created_at=str(row[8]),
            updated_at=str(row[9]),
            committed_at=None if row[10] is None else str(row[10]),
        )

    # -- opportunity / expression-need write faces --------------------------

    def record_opportunity(
        self,
        *,
        source_turn_id: TurnId | None,
        target_type: str,
        target_id: TargetId,
        opportunity_type: str,
        target_explicitness: str,
        attempt_observed: bool,
        alternative_realizations_allowed: bool,
        teaching_moment_id: str | None = None,
        learning_opportunity_id: LearningOpportunityId | None = None,
    ) -> Result[LearningOpportunityId]:
        """Durable LearningOpportunityRecord (DATA_MODEL §7) — the
        "genuine Opportunity" leg of the DOMAIN_MODEL §6 negative
        evidence rule."""

        opportunity_id = (
            learning_opportunity_id
            if learning_opportunity_id is not None
            else LearningOpportunityId(f"lo-{uuid.uuid4().hex}")
        )
        try:
            with short_transaction(self._conn):
                self._require_current_epoch()
                self._conn.execute(
                    "INSERT INTO learning_opportunity_record ("
                    " learning_opportunity_id, source_turn_id,"
                    " teaching_moment_id, target_type, target_id,"
                    " opportunity_type, target_explicitness,"
                    " attempt_observed, alternative_realizations_allowed,"
                    " created_at"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        opportunity_id,
                        source_turn_id,
                        teaching_moment_id,
                        target_type,
                        target_id,
                        opportunity_type,
                        target_explicitness,
                        1 if attempt_observed else 0,
                        1 if alternative_realizations_allowed else 0,
                        _now(),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            return _err(DomainErrorCode.CONFLICT, str(exc))
        return Ok(opportunity_id)

    def record_expression_need(
        self,
        *,
        source_turn_id: TurnId,
        intended_meaning: str,
        context_summary: str | None = None,
        recurrence_count: int = 1,
        personal_relevance: str = "NORMAL",
        resolved_resources: tuple[str, ...] | None = None,
        status: str = "OPEN",
    ) -> Result[str]:
        """Durable ExpressionNeed (DATA_MODEL §10) — Personal Expression
        Frontier. NOT negative mastery evidence: this write face is fully
        separate from the evidence kernel and the negative-evidence gate
        never consults it."""

        expression_need_id = f"xn-{uuid.uuid4().hex}"
        try:
            with short_transaction(self._conn):
                self._require_current_epoch()
                self._conn.execute(
                    "INSERT INTO expression_need ("
                    " expression_need_id, source_turn_id, intended_meaning,"
                    " context_summary, recurrence_count,"
                    " personal_relevance, last_seen_at, resolved_resources,"
                    " status"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        expression_need_id,
                        source_turn_id,
                        intended_meaning,
                        context_summary,
                        recurrence_count,
                        personal_relevance,
                        _now(),
                        (
                            json.dumps(
                                list(resolved_resources), sort_keys=True
                            )
                            if resolved_resources is not None
                            else None
                        ),
                        status,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            return _err(DomainErrorCode.CONFLICT, str(exc))
        return Ok(expression_need_id)

    # -- supersede / invalidate (STATE_MACHINES §18) ------------------------

    def supersede_claim(
        self,
        superseded_claim_id: EvidenceClaimId,
        replacement: EvidenceClaimView,
        *,
        evaluator_version: EvaluatorVersion,
        evaluator_id: str = "learning-store-v1",
    ) -> Result[EvidenceClaimId]:
        """Supersede one ACTIVE claim with a re-evaluated replacement
        (STATE_MACHINES §18 correction semantics; explicit supersede —
        e.g. a late ClientRenderAck re-evaluation, RA §6).

        One short transaction: validate the replacement (the §6
        negative-evidence rule applies to it too) → insert the new claim
        with status ACTIVE and supersedes_claim_id pointing at the old
        one → flip the old claim to SUPERSEDED → advance the watermark
        (a new ACTIVE claim row is durable evidence the P2B rebuild must
        see). The old row stays fully traceable (append-only)."""

        new_claim_id = EvidenceClaimId(
            "ecl-"
            + _stable_digest(
                superseded_claim_id,
                replacement.claim_role or "",
                replacement.performance_type.value,
                replacement.polarity.value,
                replacement.outcome.value,
            )[:24]
        )
        try:
            with short_transaction(self._conn):
                self._require_current_epoch()
                old = self._claim_row(superseded_claim_id)
                if old is None:
                    return _err(
                        DomainErrorCode.NOT_FOUND,
                        f"claim not found: {superseded_claim_id}",
                    )
                if str(old["status"]) != EvidenceStatus.ACTIVE.value:
                    return _err(
                        DomainErrorCode.CONFLICT,
                        "only an ACTIVE claim can be superseded (current:"
                        f" {old['status']})",
                    )
                refusal = self._claim_refusal(
                    replacement, TargetId(str(old["target_id"]))
                )
                if refusal is not None:
                    return Err(refusal)

                self._insert_claim(
                    claim=replacement,
                    group=EvidenceGroupRecord(
                        evidence_group_id=EvidenceGroupId(
                            str(old["evidence_group_id"])
                        ),
                        moment_id=(
                            None
                            if old["teaching_moment_id"] is None
                            else MomentId(str(old["teaching_moment_id"]))
                        ),
                        attempt_id=(
                            None
                            if old["attempt_id"] is None
                            else AttemptId(str(old["attempt_id"]))
                        ),
                        target_id=TargetId(str(old["target_id"])),
                        evaluator_version=evaluator_version,
                        claims=(replacement,),
                    ),
                    source_turn_id=TurnId(str(old["source_turn_id"])),
                    conversation_id=str(old["conversation_id"]),
                    persona_id=(
                        None
                        if old["persona_id"] is None
                        else str(old["persona_id"])
                    ),
                    evaluator_id=evaluator_id,
                    supersedes_claim_id=superseded_claim_id,
                    claim_id=new_claim_id,
                )
                self._conn.execute(
                    "UPDATE evidence_claim SET status = 'SUPERSEDED'"
                    " WHERE evidence_claim_id = ? AND status = 'ACTIVE'",
                    (superseded_claim_id,),
                )
                self._bump_watermark()
                return Ok(new_claim_id)
        except sqlite3.IntegrityError as exc:
            return _err(DomainErrorCode.CONFLICT, str(exc))

    def invalidate_claim(
        self, claim_id: EvidenceClaimId
    ) -> Result[EvidenceClaimId]:
        """Invalidate one ACTIVE claim (STATE_MACHINES §18): the row
        stays append-only traceable with status INVALIDATED and leaves
        the estimating set.

        F2 (adjudicated in the P2B mother decision DEC-…eaaa5a1d.26):
        the watermark is the durable EVIDENCE-CHANGE sequence number —
        commit / supersede / invalidate ALL advance it. An invalidation
        durably changes the ACTIVE claim set the projection rebuilds
        from, so it moves the sequence exactly like a supersede (the
        former P2A self-adjudication "invalidate adds no evidence row →
        no watermark move" is superseded by this semantics upgrade; the
        old pin was revised with it)."""

        with short_transaction(self._conn):
            self._require_current_epoch()
            row = self._claim_row(claim_id)
            if row is None:
                return _err(
                    DomainErrorCode.NOT_FOUND, f"claim not found: {claim_id}"
                )
            if str(row["status"]) != EvidenceStatus.ACTIVE.value:
                return _err(
                    DomainErrorCode.CONFLICT,
                    "only an ACTIVE claim can be invalidated (current:"
                    f" {row['status']})",
                )
            self._conn.execute(
                "UPDATE evidence_claim SET status = 'INVALIDATED'"
                " WHERE evidence_claim_id = ? AND status = 'ACTIVE'",
                (claim_id,),
            )
            self._bump_watermark()
        return Ok(claim_id)

    # -- read faces ----------------------------------------------------------

    def get_analysis_artifact(
        self, analysis_id: AnalysisId
    ) -> Result[AnalysisArtifactRecord | None]:
        row = self._artifact_row(analysis_id)
        return Ok(None if row is None else self._artifact_record(row))

    def get_analysis_for_turn(
        self, turn_id: TurnId
    ) -> Result[AnalysisArtifactRecord | None]:
        row = self._artifact_row_for(
            turn_id, ANALYSIS_TYPE_LEARNING_EVIDENCE,
            DETERMINISTIC_ANALYSIS_PRODUCER_ID,
        )
        return Ok(None if row is None else self._artifact_record(row))

    def get_evidence_group(
        self, evidence_group_id: EvidenceGroupId
    ) -> Result[tuple[GroupRecord, tuple[ClaimRecord, ...]] | None]:
        group = self._group_row(evidence_group_id)
        if group is None:
            return Ok(None)
        # P2B fix: this read face used "SELECT *" and fed the raw tuple
        # into the name-indexed claim parser — it had no claiming caller
        # in P2A, so the breakage was latent. Pinned to the shared
        # literal select + column whitelist like every other claim read.
        rows = self._conn.execute(
            _CLAIM_SELECT + " WHERE evidence_group_id = ?"
            " ORDER BY created_at, evidence_claim_id",
            (evidence_group_id,),
        ).fetchall()
        return Ok(
            (
                self._group_record(group),
                tuple(
                    self._claim_record(
                        dict(zip(_CLAIM_COLUMNS, row, strict=True))
                    )
                    for row in rows
                ),
            )
        )

    def get_claim(self, claim_id: EvidenceClaimId) -> Result[ClaimRecord | None]:
        row = self._claim_row(claim_id)
        return Ok(None if row is None else self._claim_record(row))

    def supersede_chain(
        self, claim_id: EvidenceClaimId
    ) -> Result[tuple[ClaimRecord, ...]]:
        """Walk supersedes_claim_id from the newest claim back to the
        root (newest → oldest); every link stays traceable."""

        chain: list[ClaimRecord] = []
        current: EvidenceClaimId | None = claim_id
        seen: set[str] = set()
        while current is not None:
            if current in seen:
                return _err(
                    DomainErrorCode.CONFLICT,
                    f"supersede cycle detected at {current}",
                )
            seen.add(current)
            row = self._claim_row(current)
            if row is None:
                return _err(
                    DomainErrorCode.NOT_FOUND, f"claim not found: {current}"
                )
            chain.append(self._claim_record(row))
            current = (
                EvidenceClaimId(str(row["supersedes_claim_id"]))
                if row["supersedes_claim_id"] is not None
                else None
            )
        return Ok(tuple(chain))

    def get_evidence_watermark(self) -> int:
        """Current durable watermark for the store's user scope
        (0 when no CP1 has committed yet)."""

        row = self._conn.execute(
            "SELECT watermark FROM evidence_watermark WHERE user_scope_id = ?",
            (self._user_scope_id,),
        ).fetchone()
        return 0 if row is None else int(row[0])

    def get_commit_for_group(
        self, evidence_group_id: EvidenceGroupId
    ) -> Result[tuple[str, int] | None]:
        """(commit_id, watermark_after) for a committed group, or None."""

        row = self._commit_row_by_group(evidence_group_id)
        if row is None:
            return Ok(None)
        return Ok((str(row[0]), int(row[4])))

    # -- internals -----------------------------------------------------------

    def _bump_watermark(self) -> int:
        """Advance the durable watermark inside the caller's transaction
        (RA §4 step 4 "materialize new evidence watermark")."""

        self._conn.execute(
            "INSERT INTO evidence_watermark (user_scope_id, watermark,"
            " updated_at) VALUES (?, 1, ?)"
            " ON CONFLICT(user_scope_id) DO UPDATE SET"
            " watermark = watermark + 1, updated_at = excluded.updated_at",
            (self._user_scope_id, _now()),
        )
        row = self._conn.execute(
            "SELECT watermark FROM evidence_watermark"
            " WHERE user_scope_id = ?",
            (self._user_scope_id,),
        ).fetchone()
        assert row is not None  # upsert above guarantees the row
        return int(row[0])

    def _claim_refusal(
        self,
        claim: EvidenceClaimView,
        target_id: TargetId,
        group: EvidenceGroupRecord | None = None,
    ) -> DomainError | None:
        """Pure-side validation + the §6 negative-evidence gate for one
        proposed claim. The durable opportunity lookup happens here (the
        gate's decision point is Learning's validation face).

        P3-1B addition — LOR semantic association (TASK-…2.2 ③): a claim
        that names an ``opportunity_id`` is checked against the durable
        LearningOpportunityRecord it points at: the record must exist, its
        ``target_type`` / ``target_id`` must be the claim's own target, and
        its ``teaching_moment_id`` provenance must be the claim's moment.
        An unlinked claim (no opportunity_id) keeps the pre-P3-1B behavior
        exactly. Teaching never validates this itself — Learning owns the
        LOR and is the only side that may read it (the AST pin)."""

        if claim.status is not EvidenceStatus.ACTIVE:
            return DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    "new claims must be ACTIVE (got"
                    f" {claim.status.value}); corrections go through"
                    " supersede"
                ),
            )
        if claim.outcome.value not in _CLAIM_OUTCOME_VALUES:
            return DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    f"outcome={claim.outcome.value} is a STATE_MACHINES §5"
                    " attempt word; the DATA_MODEL §6 claim outcome"
                    " vocabulary is SUCCESS/PARTIAL/FAILURE/ABSTAIN"
                ),
            )
        if not 0.0 <= claim.evaluator_confidence <= 1.0:
            return DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    "evaluator_confidence must be within [0, 1] (got"
                    f" {claim.evaluator_confidence})"
                ),
            )
        claim_target = (
            str(target_id) if claim.target_id is None else claim.target_id
        )
        if claim.opportunity_id is not None:
            refusal = self._opportunity_link_refusal(claim, claim_target, group)
            if refusal is not None:
                return refusal
        has_opportunity = (
            self._conn.execute(
                "SELECT 1 FROM learning_opportunity_record"
                " WHERE target_type = ? AND target_id = ? LIMIT 1",
                (claim.scope, claim_target),
            ).fetchone()
            is not None
        )
        return negative_evidence_refusal(claim, has_opportunity)

    def _opportunity_link_refusal(
        self,
        claim: EvidenceClaimView,
        claim_target: str,
        group: EvidenceGroupRecord | None,
    ) -> DomainError | None:
        """The LOR semantic association of one claim (see _claim_refusal).

        Three facts are checked:

        - the opportunity exists (a claim may not invent provenance);
        - its ``teaching_moment_id`` agrees with the claim's moment (the
          teaching-flow provenance rule of DEC-…2babb21e.5);
        - its target agrees with the claim's target — for the claim that
          speaks about the opportunity's own target. The one deliberate
          relaxation is the CAPABILITY_LINKAGE claim of an alternative
          realization (STATE_MACHINES §5 Resource Practice): it speaks about
          the CAPABILITY that the opportunity's RESOURCE realizes, so it is
          linked to the same opportunity while carrying a different target;
          requiring target equality there would forbid exactly the mapping
          §5 mandates. The relaxation is narrow — a linkage claim must still
          be a CAPABILITY claim and must still carry the same moment.
        """

        row = self._conn.execute(
            "SELECT target_type, target_id, teaching_moment_id"
            " FROM learning_opportunity_record WHERE learning_opportunity_id = ?",
            (claim.opportunity_id,),
        ).fetchone()
        if row is None:
            return DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    "claim names opportunity"
                    f" {claim.opportunity_id} but no LearningOpportunityRecord"
                    " exists for it (DATA_MODEL §7)"
                ),
            )
        capability_linkage = claim.claim_role == CAPABILITY_LINKAGE_CLAIM_ROLE
        if capability_linkage:
            if claim.scope != "CAPABILITY":
                return DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        "the capability-linkage claim of opportunity"
                        f" {claim.opportunity_id} must speak about a"
                        f" CAPABILITY, got scope={claim.scope!r}"
                    ),
                )
        elif str(row[0]) != claim.scope or str(row[1]) != claim_target:
            return DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    "the linked LearningOpportunityRecord targets"
                    f" {row[0]}/{row[1]} but the claim targets"
                    f" {claim.scope}/{claim_target} — a claim and its"
                    " opportunity must be about the same target"
                    " (DATA_MODEL §6/§7)"
                ),
            )
        if group is not None and group.moment_id is not None:
            if str(row[2] or "") != str(group.moment_id):
                return DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        "the linked LearningOpportunityRecord carries"
                        f" teaching_moment_id={row[2]!r} but the claim's"
                        f" moment is {group.moment_id} — teaching-claim"
                        " provenance must agree (DEC-…2babb21e.5 LOR"
                        " semantic association)"
                    ),
                )
        return None

    def _insert_claim(
        self,
        *,
        claim: EvidenceClaimView,
        group: EvidenceGroupRecord,
        source_turn_id: TurnId,
        conversation_id: str,
        persona_id: str | None,
        evaluator_id: str,
        supersedes_claim_id: EvidenceClaimId | None,
        claim_id: EvidenceClaimId | None = None,
    ) -> None:
        """Insert one evidence_claim row with the documented default
        fill for columns the Phase 0 view does not carry."""

        row_id = (
            claim_id
            if claim_id is not None
            else EvidenceClaimId(f"ecl-{uuid.uuid4().hex}")
        )
        self._conn.execute(
            "INSERT INTO evidence_claim ("
            " evidence_claim_id, evidence_group_id, opportunity_id,"
            " target_type, target_id, performance_type, polarity,"
            " outcome, qualifiers, evidence_modality, elicitation_type,"
            " spontaneity, support_level, answer_exposure_state,"
            " exposure_estimate_id, support_attribution_certainty,"
            " support_attribution_basis, accuracy, pragmatic_fit,"
            " fluency, error_attribution, delay_seconds, context_novelty,"
            " persona_novelty, evidence_modality_novelty,"
            " capability_evidence_basis, source_turn_id, conversation_id,"
            " persona_id, teaching_moment_id, evaluator_id,"
            " evaluator_version, evaluator_confidence, status,"
            " supersedes_claim_id, attempt_id, claim_role, created_at"
            ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,"
            "?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                row_id,
                group.evidence_group_id,
                # P3-1B: an unlinked claim keeps NULL (Phase 0 view);
                # a teaching claim names its durable LearningOpportunity.
                (
                    None
                    if claim.opportunity_id is None
                    else str(claim.opportunity_id)
                ),
                claim.scope,
                # P3-1B: a claim may target its own id (the capability-
                # linkage claim points at the CAPABILITY, not at the
                # RESOURCE the group is about).
                group.target_id if claim.target_id is None else claim.target_id,
                claim.performance_type.value,
                claim.polarity.value,
                claim.outcome.value,
                json.dumps(
                    [qualifier.value for qualifier in claim.qualifiers]
                ),
                claim.evidence_modality.value,
                "NATURAL",  # default fill (see module docstring)
                "SPONTANEOUS",  # default fill (BF-01 v1.1 vocabulary)
                claim.support.value,
                claim.exposure.value,
                None,
                0.0,
                "UNSPECIFIED",
                claim.accuracy,
                claim.pragmatic_fit,
                None,  # fluency: TEXT modality must not fake speaking
                claim.error_attribution.value,
                None,  # delay_seconds
                0.0,
                0.0,
                0.0,
                None,  # capability_evidence_basis
                source_turn_id,
                conversation_id,
                persona_id,
                group.moment_id,
                evaluator_id,
                group.evaluator_version,  # NewType(str) — no .value
                claim.evaluator_confidence,
                EvidenceStatus.ACTIVE.value,
                supersedes_claim_id,
                group.attempt_id,
                claim.claim_role,
                _now(),
            ),
        )

    def _projection_rows(self) -> list[sqlite3.Row]:
        """The §11 projection rows in the read's deterministic order —
        shared by get_learning_snapshot (the consistency gate) and
        stale_projection_targets (the repair face), so the two can never
        disagree about which rows lag."""

        return self._conn.execute(
            "SELECT target_type, target_id, evidence_modality, state_json"
            " FROM learner_target_state WHERE user_scope_id = ?"
            " ORDER BY target_type, target_id, evidence_modality",
            (self._user_scope_id,),
        ).fetchall()

    def _artifact_row_for(
        self, turn_id: TurnId, analysis_type: str, producer_id: str
    ) -> sqlite3.Row | None:
        return self._conn.execute(
            "SELECT analysis_id, turn_id, analysis_type, producer_id,"
            " producer_version, structured_proposal, confidence, status,"
            " created_at FROM analysis_artifact"
            " WHERE turn_id = ? AND analysis_type = ? AND producer_id = ?",
            (turn_id, analysis_type, producer_id),
        ).fetchone()

    def _artifact_row(self, analysis_id: AnalysisId) -> sqlite3.Row | None:
        # Column order mirrors the SELECT below.
        return self._conn.execute(
            "SELECT analysis_id, turn_id, analysis_type, producer_id,"
            " producer_version, structured_proposal, confidence, status,"
            " created_at FROM analysis_artifact WHERE analysis_id = ?",
            (analysis_id,),
        ).fetchone()

    def _artifact_record(self, row: sqlite3.Row) -> AnalysisArtifactRecord:
        return AnalysisArtifactRecord(
            analysis_id=AnalysisId(str(row[0])),
            turn_id=TurnId(str(row[1])),
            analysis_type=str(row[2]),
            producer_id=str(row[3]),
            producer_version=str(row[4]),
            structured_proposal=str(row[5]),
            confidence=float(row[6]),
            status=str(row[7]),
            created_at=str(row[8]),
        )

    @staticmethod
    def _proposal_from_row(row: sqlite3.Row) -> LearningEvidenceProposal:
        return LearningEvidenceProposal(
            analysis_id=AnalysisId(str(row[0])),
            turn_id=TurnId(str(row[1])),
            producer_id=str(row[3]),
            producer_version=str(row[4]),
            structured_proposal=str(row[5]),
            confidence=float(row[6]),
        )

    def _commit_row_by_group(
        self, evidence_group_id: EvidenceGroupId
    ) -> sqlite3.Row | None:
        # Column order: commit_id, group, analysis_id, scope,
        # watermark_after, committed_at.
        return self._conn.execute(
            "SELECT evidence_commit_id, evidence_group_id, analysis_id,"
            " user_scope_id, watermark_after, committed_at"
            " FROM evidence_commit WHERE evidence_group_id = ?",
            (evidence_group_id,),
        ).fetchone()

    def _commit_row_by_analysis(
        self, analysis_id: AnalysisId
    ) -> sqlite3.Row | None:
        return self._conn.execute(
            "SELECT evidence_commit_id, evidence_group_id, analysis_id,"
            " user_scope_id, watermark_after, committed_at"
            " FROM evidence_commit WHERE analysis_id = ?",
            (analysis_id,),
        ).fetchone()

    def _group_row(self, evidence_group_id: EvidenceGroupId) -> sqlite3.Row | None:
        # Column order: group_id, source_turn_id, conversation_id,
        # persona_id, teaching_moment_id, evidence_modality, created_at.
        return self._conn.execute(
            "SELECT evidence_group_id, source_turn_id, conversation_id,"
            " persona_id, teaching_moment_id, evidence_modality, created_at"
            " FROM evidence_group WHERE evidence_group_id = ?",
            (evidence_group_id,),
        ).fetchone()

    @staticmethod
    def _group_record(row: sqlite3.Row) -> GroupRecord:
        return GroupRecord(
            evidence_group_id=EvidenceGroupId(str(row[0])),
            source_turn_id=TurnId(str(row[1])),
            conversation_id=str(row[2]),
            persona_id=None if row[3] is None else str(row[3]),
            teaching_moment_id=None if row[4] is None else str(row[4]),
            evidence_modality=str(row[5]),
            created_at=str(row[6]),
        )

    def _claim_row(self, claim_id: EvidenceClaimId) -> dict[str, object] | None:
        """Named row (column order pinned by _CLAIM_COLUMNS; named access
        keeps the 38-column surface index-error-free)."""

        row = self._conn.execute(
            _CLAIM_SELECT + " WHERE evidence_claim_id = ?",
            (claim_id,),
        ).fetchone()
        if row is None:
            return None
        return dict(zip(_CLAIM_COLUMNS, row, strict=True))

    def _claim_records_for(
        self,
        target_type: str,
        target_id: TargetId,
        evidence_modality: str,
    ) -> tuple[ClaimRecord, ...]:
        """ACTIVE claims of one §11 scope key (target_type × target_id ×
        modality) in deterministic order — the rebuild's input set
        (BF-01 §29: only ACTIVE evidence enters estimation)."""

        rows = self._conn.execute(
            _CLAIM_SELECT
            + " WHERE target_type = ? AND target_id = ?"
            " AND evidence_modality = ? AND status = 'ACTIVE'"
            " ORDER BY created_at, evidence_claim_id",
            (target_type, target_id, evidence_modality),
        ).fetchall()
        return tuple(
            self._claim_record(dict(zip(_CLAIM_COLUMNS, row, strict=True)))
            for row in rows
        )

    @staticmethod
    def _claim_record(row: dict[str, object]) -> ClaimRecord:
        def text(key: str) -> str:
            return str(row[key])

        def opt_text(key: str) -> str | None:
            return None if row[key] is None else str(row[key])

        def number(key: str) -> float:
            return float(cast(float, row[key]))

        def opt_number(key: str) -> float | None:
            return None if row[key] is None else float(cast(float, row[key]))

        def opt_int(key: str) -> int | None:
            return None if row[key] is None else int(cast(int, row[key]))

        return ClaimRecord(
            evidence_claim_id=EvidenceClaimId(text("evidence_claim_id")),
            evidence_group_id=EvidenceGroupId(
                text("evidence_group_id")
            ),
            opportunity_id=opt_text("opportunity_id"),
            target_type=text("target_type"),
            target_id=text("target_id"),
            performance_type=text("performance_type"),
            polarity=text("polarity"),
            outcome=text("outcome"),
            qualifiers=tuple(json.loads(text("qualifiers"))),
            evidence_modality=text("evidence_modality"),
            elicitation_type=text("elicitation_type"),
            spontaneity=text("spontaneity"),
            support_level=text("support_level"),
            answer_exposure_state=text("answer_exposure_state"),
            exposure_estimate_id=opt_text("exposure_estimate_id"),
            support_attribution_certainty=number(
                "support_attribution_certainty"
            ),
            support_attribution_basis=text("support_attribution_basis"),
            accuracy=opt_number("accuracy"),
            pragmatic_fit=opt_number("pragmatic_fit"),
            fluency=opt_number("fluency"),
            error_attribution=opt_text("error_attribution"),
            delay_seconds=opt_int("delay_seconds"),
            context_novelty=number("context_novelty"),
            persona_novelty=number("persona_novelty"),
            evidence_modality_novelty=number("evidence_modality_novelty"),
            capability_evidence_basis=opt_text("capability_evidence_basis"),
            source_turn_id=TurnId(text("source_turn_id")),
            conversation_id=text("conversation_id"),
            persona_id=opt_text("persona_id"),
            teaching_moment_id=opt_text("teaching_moment_id"),
            evaluator_id=text("evaluator_id"),
            evaluator_version=text("evaluator_version"),
            evaluator_confidence=number("evaluator_confidence"),
            status=text("status"),
            supersedes_claim_id=(
                EvidenceClaimId(text("supersedes_claim_id"))
                if row["supersedes_claim_id"] is not None
                else None
            ),
            attempt_id=opt_text("attempt_id"),
            claim_role=opt_text("claim_role"),
            created_at=text("created_at"),
        )


def _group_modality(group: EvidenceGroupRecord) -> str:
    """Modality of a protocol-face group: the shared claim modality (a
    group is one observable behavior in one modality)."""

    if group.claims:
        return group.claims[0].evidence_modality.value
    return "TEXT_PRODUCTION"


# -- P4-0 ①: the durable teaching-evidence proposal payload -----------------


@dataclass(frozen=True)
class _TeachingEvidenceCommitContext:
    """The commit context a durable proposal carries (payload ``commit``).

    Everything ``commit_evidence_group`` needs beyond the claims: the
    deterministic group id, the turn/conversation the evidence belongs to,
    the persona (when the moment had one) and the evaluator provenance.
    Keeping it in the payload is what makes the durable row self-contained
    — a retry after the process died reads no teaching-owned table.
    """

    evidence_group_id: str
    source_turn_id: str
    conversation_id: str
    persona_id: str | None
    evaluator_id: str


def _claim_document(claim: EvidenceClaimView) -> dict[str, object]:
    """One claim as canonical JSON data (enum words, never enum objects)."""

    return {
        "accuracy": claim.accuracy,
        "claim_role": claim.claim_role,
        "error_attribution": claim.error_attribution.value,
        "evidence_claim_id": claim.evidence_claim_id,
        "evidence_modality": claim.evidence_modality.value,
        "evaluator_confidence": claim.evaluator_confidence,
        "exposure": claim.exposure.value,
        "opportunity_id": (
            None if claim.opportunity_id is None else str(claim.opportunity_id)
        ),
        "outcome": claim.outcome.value,
        "performance_type": claim.performance_type.value,
        "polarity": claim.polarity.value,
        "pragmatic_fit": claim.pragmatic_fit,
        "provenance": claim.provenance,
        "qualifiers": [qualifier.value for qualifier in claim.qualifiers],
        "scope": claim.scope,
        "status": claim.status.value,
        "support": claim.support.value,
        "target_id": claim.target_id,
    }


def _claim_from_document(document: Mapping[str, object]) -> EvidenceClaimView:
    """Rebuild one claim view from its payload document (the exact inverse
    of :func:`_claim_document`; an unknown word raises ValueError, which the
    caller surfaces as a refusal — never a silent default)."""

    qualifiers = cast(Sequence[object], document["qualifiers"])
    accuracy = document["accuracy"]
    pragmatic_fit = document["pragmatic_fit"]
    opportunity_id = document["opportunity_id"]
    target_id = document["target_id"]
    return EvidenceClaimView(
        evidence_claim_id=str(document["evidence_claim_id"]),
        claim_role=str(document["claim_role"]),
        scope=str(document["scope"]),
        performance_type=PerformanceType(str(document["performance_type"])),
        evidence_modality=EvidenceModality(str(document["evidence_modality"])),
        qualifiers=tuple(
            EvidenceQualifier(str(qualifier)) for qualifier in qualifiers
        ),
        polarity=EvidencePolarity(str(document["polarity"])),
        outcome=AttemptOutcome(str(document["outcome"])),
        support=SupportLevel(str(document["support"])),
        exposure=ExposureLevel(str(document["exposure"])),
        evaluator_confidence=float(
            cast(float, document["evaluator_confidence"])
        ),
        error_attribution=ErrorAttribution(str(document["error_attribution"])),
        accuracy=None if accuracy is None else float(cast(float, accuracy)),
        pragmatic_fit=(
            None if pragmatic_fit is None else float(cast(float, pragmatic_fit))
        ),
        status=EvidenceStatus(str(document["status"])),
        provenance=str(document["provenance"]),
        opportunity_id=(
            None
            if opportunity_id is None
            else LearningOpportunityId(str(opportunity_id))
        ),
        target_id=None if target_id is None else str(target_id),
    )


def _teaching_evidence_payload(
    *,
    attempt_id: str,
    claims: tuple[EvidenceClaimView, ...],
    evaluator_id: str,
    evaluator_version: str,
    target_id: str,
    source_turn_id: TurnId,
    conversation_id: str,
    persona_id: str | None,
) -> str:
    """The durable payload of one teaching-evidence proposal: the claim
    views Learning converted the attempt into, plus their commit context.

    Canonical JSON (sorted keys, fixed separators) so the same facts always
    produce the same payload — and therefore the same ``payload_hash``,
    which is what makes an idempotent replay checkable.
    """

    return json.dumps(
        {
            "attempt_id": attempt_id,
            "claims": [_claim_document(claim) for claim in claims],
            "commit": {
                "conversation_id": conversation_id,
                "evaluator_id": evaluator_id,
                "evaluator_version": evaluator_version,
                "evidence_group_id": teaching_evidence_group_id(attempt_id),
                "persona_id": persona_id,
                "source_turn_id": str(source_turn_id),
                "target_id": target_id,
            },
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _teaching_evidence_document(payload: str) -> dict[str, object]:
    document: dict[str, object] = json.loads(payload)
    return document


def _teaching_evidence_commit_context(
    row: Sequence[object],
) -> _TeachingEvidenceCommitContext:
    """The commit context of one durable proposal row (column order pinned
    by ``_proposal_row``: moment_id=3, payload=5)."""

    commit = cast(
        Mapping[str, object],
        _teaching_evidence_document(str(row[5]))["commit"],
    )
    persona_id = commit["persona_id"]
    return _TeachingEvidenceCommitContext(
        evidence_group_id=str(commit["evidence_group_id"]),
        source_turn_id=str(commit["source_turn_id"]),
        conversation_id=str(commit["conversation_id"]),
        persona_id=None if persona_id is None else str(persona_id),
        evaluator_id=str(commit["evaluator_id"]),
    )


def _teaching_evidence_group(
    row: Sequence[object],
    context: _TeachingEvidenceCommitContext,
) -> EvidenceGroupRecord:
    """Rebuild the §6 group a durable proposal commits into — from the
    payload alone (no teaching-side object, no cross-domain read)."""

    document = _teaching_evidence_document(str(row[5]))
    commit = cast(Mapping[str, object], document["commit"])
    claims = cast(Sequence[object], document["claims"])
    return EvidenceGroupRecord(
        evidence_group_id=EvidenceGroupId(context.evidence_group_id),
        moment_id=MomentId(str(row[3])),
        attempt_id=AttemptId(str(row[1])),
        target_id=TargetId(str(commit["target_id"])),
        evaluator_version=EvaluatorVersion(str(commit["evaluator_version"])),
        claims=tuple(
            _claim_from_document(cast(Mapping[str, object], item))
            for item in claims
        ),
    )


def _parse_proposal(structured_proposal: str) -> dict[str, object]:
    parsed: dict[str, object] = json.loads(structured_proposal)
    return parsed


def _proposal_refusal(
    parsed: dict[str, object], turn: CanonicalTurnSlice
) -> DomainError | None:
    """Learning's decision on the deterministic proposal (DOMAIN_MODEL
    §18): unobservable proposals are REJECTED; the utterance hash binds
    the artifact to the canonical turn (a stale/mismatched artifact never
    commits)."""

    observable = bool(parsed.get("observable", False))
    if not observable:
        return DomainError(
            code=DomainErrorCode.VALIDATION_FAILED,
            message=(
                "proposal is not an observable behavior — REJECTED"
                " (DOMAIN_MODEL §18)"
            ),
        )
    utterance_hash = str(parsed.get("utterance_sha256", ""))
    text = turn.user_turn.raw_content
    if utterance_hash != hashlib.sha256(text.encode("utf-8")).hexdigest():
        return DomainError(
            code=DomainErrorCode.VALIDATION_FAILED,
            message=(
                "proposal utterance_sha256 does not match the canonical"
                " turn — artifact/turn binding failed"
            ),
        )
    return None


def _silent_claim_for_proposal(
    parsed: dict[str, object], turn: CanonicalTurnSlice
) -> tuple[EvidenceClaimView | None, DomainError | None]:
    """The target claim a durable proposal carries, if any (P5-2; admission
    gate added by P5-R).

    The producer records the *facts* of a resolved observation (which
    target, which form, which rule); this function rebuilds the
    TargetMatchObservation from **the durable document plus the canonical
    turn** and re-runs admission **rules 1-3** before any claim exists
    (elc.learning.target_match.admitted_for_evidence) — so a document that
    reaches the kernel from anywhere else (hand-edited, stale, fabricated)
    cannot mint a claim a whole-sentence form-class RESOURCE match would not
    have minted. The conversion itself stays Learning's (the
    teaching-evidence pattern: facts in, Learning decides what they are
    worth).

    **What this layer does and does not re-check (declared).** The re-check
    here is exactly the rebuild + rules 1-3: rules 4 (no open TeachingMoment
    for the target) and 5 (readable supply) are **live-leg guards** and are
    not applied at this layer, which holds neither the teaching nor the
    supply port. ``target_type`` is likewise read as a **document-declared
    fact**: the kernel takes the rebuilt observation's ``RESOURCE`` at its
    word and performs no type-identity or supply-identity check here — the
    supply gate is the read face
    (elc.learning.silent_evidence.ContentBackedTargetSupply), not the kernel
    (the teaching-provider division of labour).

    ``(None, None)`` in three cases, all observation-only (zero claim, zero
    LearnerState change): the Phase 2 target-less proposal, an unreadable
    target document (REJECT — a refusal, never a silent skip), and a match
    that fails admission.
    """

    target = parsed.get("target")
    if target is None:
        return None, None
    if not isinstance(target, Mapping):
        return None, DomainError(
            code=DomainErrorCode.VALIDATION_FAILED,
            message=(
                "proposal target is not a document — REJECTED"
                " (DOMAIN_MODEL §18)"
            ),
        )
    try:
        resolution = resolution_from_document(target)
    except (KeyError, ValueError) as exc:
        return None, DomainError(
            code=DomainErrorCode.VALIDATION_FAILED,
            message=(
                "proposal target is not readable as a resolution document:"
                f" {exc!r} — REJECTED (DOMAIN_MODEL §18)"
            ),
        )
    observation = observe_target_match(
        turn_id=str(turn.turn_id),
        utterance=turn.user_turn.raw_content,
        resolution=resolution,
    )
    if not admitted_for_evidence(observation, turn.user_turn.raw_content):
        # Observation-only: the durable document recorded a match that is
        # not evidence (embedded span, slot-only, CAPABILITY, …). Nothing is
        # refused — the turn is simply not a claim, the Phase 2 shape.
        return None, None
    try:
        claim = claim_for_silent_observation(
            observation,
            evidence_modality=str(
                parsed.get("evidence_modality", SILENT_EVIDENCE_MODALITY)
            ),
        )
    except ValueError as exc:
        return None, DomainError(
            code=DomainErrorCode.VALIDATION_FAILED,
            message=(
                "proposal evidence_modality is outside the canonical"
                f" vocabulary: {exc!r} — REJECTED (DOMAIN_MODEL §18)"
            ),
        )
    return claim, None


def _stable_digest(*parts: str) -> str:
    hasher = hashlib.sha256()
    for part in parts:
        hasher.update(part.encode("utf-8"))
        hasher.update(b"\x1f")
    return hasher.hexdigest()


# -- P2B: estimator view adapter + §11 document (de)serialization ----------


def _estimator_view(claim: ClaimRecord) -> EstimatorClaimView:
    """Adapt one durable §6 claim row to the BF-01 §7 estimator view.

    Column mapping (implementation-defined per DATA_MODEL §27):
    - opportunity_type ← elicitation_type (the §7 opportunity
      vocabulary root-shares the elicitation words; the protocol-face
      default fill is 'NATURAL' — module docstring).
    - timestamp ← created_at (the claim's durable evidence time).
    - error_attribution None → 'UNKNOWN' (BF-01 §6 default multiplier).
    - context_key / realization_key are None: the §6 column set carries
      novelty reals (context_novelty / persona_novelty /
      evidence_modality_novelty), not context/realization keys, so the
      estimator's documented fallbacks apply ("context:unknown" /
      "realization:unknown"; qualifier-driven novel: fallbacks still
      fire). Diversity therefore rides conversation/day/persona until a
      later migration adds the keys.
    """

    return EstimatorClaimView(
        group_id=claim.evidence_group_id,
        timestamp=claim.created_at,
        performance_type=claim.performance_type,
        polarity=claim.polarity,
        outcome=claim.outcome,
        evaluator_confidence=claim.evaluator_confidence,
        support_level=claim.support_level,
        exposure_level=claim.answer_exposure_state,
        opportunity_type=claim.elicitation_type,
        qualifiers=claim.qualifiers,
        error_attribution=claim.error_attribution or "UNKNOWN",
        accuracy=claim.accuracy,
        pragmatic_fit=claim.pragmatic_fit,
        conversation_id=claim.conversation_id,
        teaching_moment_id=claim.teaching_moment_id,
        persona_id=claim.persona_id,
        context_key=None,
        realization_key=None,
        target_type=claim.target_type,
        target_id=claim.target_id,
        modality=claim.evidence_modality,
        status=claim.status,
        spontaneity=claim.spontaneity,
    )


def _record_from_estimate(
    estimate: TargetStateEstimate, watermark: int, updated_at: str
) -> LearnerTargetStateRecord:
    """§11 record from the estimator output (masses stay in the
    estimator's own result; the projection surface is the §11 field
    set)."""

    dimensions = {
        name: LearnerDimensionState(
            estimate=state.estimate,
            confidence=state.confidence,
            last_relevant_evidence_at=state.last_relevant_evidence_at,
        )
        for name, state in estimate.dimensions.items()
    }
    return LearnerTargetStateRecord(
        target_type=estimate.target_type,
        target_id=TargetId(estimate.target_id),
        evidence_modality=estimate.modality,
        dimensions=dimensions,
        coverage=LearnerCoverage(
            evidence_groups=estimate.coverage.evidence_groups,
            independent_clusters=estimate.coverage.independent_clusters,
            sessions=estimate.coverage.sessions,
            days=estimate.coverage.days,
            contexts=estimate.coverage.contexts,
            personas=estimate.coverage.personas,
            realizations=estimate.coverage.realizations,
            modalities=estimate.coverage.modalities,
        ),
        freshness=LearnerFreshness(
            last_strong_retrieval_at=(
                estimate.freshness.last_strong_retrieval_at
            ),
            elapsed_since_strong_retrieval_days=(
                estimate.freshness.days_since_strong_retrieval
            ),
            freshness_band=estimate.freshness.band,
        ),
        projection=LearnerProjection(
            ability_band=estimate.projection.ability_band,
            confidence_band=estimate.projection.confidence_band,
            transfer_band=estimate.projection.transfer_band,
            support_band=estimate.projection.support_band,
            stability_band=estimate.projection.stability_band,
            learning_flags=estimate.projection.learning_flags,
        ),
        estimator_version=ESTIMATOR_PROFILE_ID,
        evidence_watermark=watermark,
        updated_at=updated_at,
    )


def _state_document(record: LearnerTargetStateRecord) -> str:
    """Canonical JSON of the §11 document (sorted keys, fixed
    separators) — the migration-0005 state_json payload."""

    return json.dumps(
        {
            "target_type": record.target_type,
            "target_id": str(record.target_id),
            "evidence_modality": record.evidence_modality,
            "dimensions": {
                name: {
                    "estimate": state.estimate,
                    "confidence": state.confidence,
                    "last_relevant_evidence_at": (
                        state.last_relevant_evidence_at
                    ),
                }
                for name, state in record.dimensions.items()
            },
            "coverage": {
                "evidence_groups": record.coverage.evidence_groups,
                "independent_clusters": (
                    record.coverage.independent_clusters
                ),
                "sessions": record.coverage.sessions,
                "days": record.coverage.days,
                "contexts": record.coverage.contexts,
                "personas": record.coverage.personas,
                "realizations": record.coverage.realizations,
                "modalities": record.coverage.modalities,
            },
            "freshness": {
                "last_strong_retrieval_at": (
                    record.freshness.last_strong_retrieval_at
                ),
                "elapsed_since_strong_retrieval_days": (
                    record.freshness.elapsed_since_strong_retrieval_days
                ),
                "freshness_band": record.freshness.freshness_band,
            },
            "projection": {
                "ability_band": record.projection.ability_band,
                "confidence_band": record.projection.confidence_band,
                "transfer_band": record.projection.transfer_band,
                "support_band": record.projection.support_band,
                "stability_band": record.projection.stability_band,
                "learning_flags": list(record.projection.learning_flags),
            },
            "meta": {
                "estimator_version": record.estimator_version,
                "evidence_watermark": record.evidence_watermark,
                "updated_at": record.updated_at,
            },
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _record_from_document(
    document: Mapping[str, object],
) -> LearnerTargetStateRecord:
    """Parse the §11 state_json document back into the typed record."""

    def count(block: Mapping[str, object], key: str) -> int:
        return int(cast(int, block[key]))

    def opt_text(block: Mapping[str, object], key: str) -> str | None:
        return None if block[key] is None else str(block[key])

    def opt_float(block: Mapping[str, object], key: str) -> float | None:
        return (
            None if block[key] is None else float(cast(float, block[key]))
        )

    dimensions_raw = cast(
        Mapping[str, Mapping[str, object]], document["dimensions"]
    )
    coverage_raw = cast(Mapping[str, object], document["coverage"])
    freshness_raw = cast(Mapping[str, object], document["freshness"])
    projection_raw = cast(Mapping[str, object], document["projection"])
    meta_raw = cast(Mapping[str, object], document["meta"])
    flags_raw = cast(Sequence[object], projection_raw["learning_flags"])
    return LearnerTargetStateRecord(
        target_type=str(document["target_type"]),
        target_id=TargetId(str(document["target_id"])),
        evidence_modality=str(document["evidence_modality"]),
        dimensions={
            name: LearnerDimensionState(
                estimate=opt_float(block, "estimate"),
                confidence=float(cast(float, block["confidence"])),
                last_relevant_evidence_at=opt_text(
                    block, "last_relevant_evidence_at"
                ),
            )
            for name, block in dimensions_raw.items()
        },
        coverage=LearnerCoverage(
            evidence_groups=count(coverage_raw, "evidence_groups"),
            independent_clusters=count(
                coverage_raw, "independent_clusters"
            ),
            sessions=count(coverage_raw, "sessions"),
            days=count(coverage_raw, "days"),
            contexts=count(coverage_raw, "contexts"),
            personas=count(coverage_raw, "personas"),
            realizations=count(coverage_raw, "realizations"),
            modalities=count(coverage_raw, "modalities"),
        ),
        freshness=LearnerFreshness(
            last_strong_retrieval_at=opt_text(
                freshness_raw, "last_strong_retrieval_at"
            ),
            elapsed_since_strong_retrieval_days=opt_float(
                freshness_raw, "elapsed_since_strong_retrieval_days"
            ),
            freshness_band=str(freshness_raw["freshness_band"]),
        ),
        projection=LearnerProjection(
            ability_band=str(projection_raw["ability_band"]),
            confidence_band=str(projection_raw["confidence_band"]),
            transfer_band=str(projection_raw["transfer_band"]),
            support_band=str(projection_raw["support_band"]),
            stability_band=str(projection_raw["stability_band"]),
            learning_flags=tuple(str(flag) for flag in flags_raw),
        ),
        estimator_version=str(meta_raw["estimator_version"]),
        evidence_watermark=int(cast(int, meta_raw["evidence_watermark"])),
        updated_at=str(meta_raw["updated_at"]),
    )
