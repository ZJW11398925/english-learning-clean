"""CP4 post-turn projection runtime — the P4-2 execution face.

The P4-0 contract (the ``elc.runtime.types`` module docstring) fixes the
semantics this module executes; nothing here re-decides them:

- **stable projection_id** — :func:`projection_id_for` *derives* the job id
  from ``(projection_type, source turn)``: one pair, one durable row, so a
  re-enqueue or a crash-gap repair addresses the same row instead of
  minting a second one (DATA_MODEL §1.2 stable ids; R-INV-012 "all side
  effects stable idempotency identity");
- **idempotent enqueue** — delegated to the durable store
  (:class:`ProjectionJobStore`), which replays an identical payload and
  refuses a different one, and never resets an existing row's state;
- **the §22.1 state machine** — PENDING → RUNNING → COMMITTED,
  FAILED_RETRYABLE → REJECTED (five words, durably CHECKed by migration
  0002 and mirrored by :class:`elc.runtime.types.ProjectionJobState`);
- **source-aware + version-aware revalidation** — every run recomputes
  :func:`turn_slice_hash` over the *current* durable CanonicalTurnSlice and
  refuses to run when it no longer matches the row's
  ``source_turn_slice_hash`` (DATA_MODEL §22.1: "不允许 blind SQL replay"),
  and it recomputes the base domain version through the type's executor
  before claiming the job (see :class:`ProjectionExecutor`);
- **CP4 never holds the ConversationCoordinatorLease** — projections run
  after the canonical turn, and the caller releases the guard first
  (RA §19 "不继续占用 ConversationCoordinatorLease"; §24.1 "CP4 projection
  在 coordinator guard release 后执行");
- **failure is not the turn's failure** — every face here returns a
  ``Result`` and nothing raises into a caller; a failed projection never
  rolls back the transcript, never re-sends the assistant message and never
  blocks the next turn (R-INV-010; RA §19/§21);
- **crash-gap** — :meth:`CP4ProjectionRuntime.ensure_missing_jobs`
  re-creates a job lost between the turn's commit points from the same
  deterministic id instead of re-deriving it from a message log.

SQL-free by construction (tests/architecture Gate item 2 scans this
package): the durable rows live in ``elc.platform.db.projection_store``
behind the :class:`ProjectionJobStore` port. This module owns the policy and
the pure derivations only — deterministic ids, the slice/base digests, the
executor dispatch, and the failure-code mapping.

Deliberately absent (P4-0 register: hard-cap counts are Calibratable):
hard-cap counters, TTL and any back-off schedule. ``attempt_count`` is
bookkeeping, never a policy input — this slice retries exactly when someone
runs the pending queue, and never on a timer (Local V1 §24.1 forbids
heartbeat/TTL machinery).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, TypeVar, runtime_checkable

from elc.platform.types import (
    ConversationId,
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    ProjectionJobId,
    Result,
    TurnId,
)
from elc.runtime.types import (
    ProjectionJobRecord,
    ProjectionJobState,
    TurnRecordData,
    TurnStatus,
)

if TYPE_CHECKING:
    # Annotations only: importing the conversation / relationship packages
    # here would deepen the runtime package's import graph for no runtime
    # benefit (the same discipline as the controller module's TYPE_CHECKING
    # imports), and every operation below is structural.
    from elc.conversation.types import CanonicalTurnSlice, ConversationRecord
    from elc.relationship.types import SamePersonaExistingRelationshipSummary

__all__ = [
    "PROJECTION_TYPE_EPISODE",
    "PROJECTION_TYPE_RELATIONSHIP",
    "SLICE_FIELD_SEPARATOR",
    "SUPPORTED_PROJECTION_TYPES",
    "CP4ProjectionRuntime",
    "ProjectionExecutor",
    "ProjectionJobStore",
    "ProjectionJobView",
    "ProjectionRunResult",
    "ProjectionTurnSource",
    "base_version_for",
    "projection_id_for",
    "turn_slice_hash",
]

#: The §22.1 ``projection_type`` of the Relationship projection
#: (DOMAIN_MODEL §5; the P4-0 contract's first live type). The vocabulary is
#: open by design — a new projection type joins by adding its executor and
#: extending :data:`SUPPORTED_PROJECTION_TYPES`, never by widening this
#: string.
PROJECTION_TYPE_RELATIONSHIP = "RELATIONSHIP"

#: The §22.1 ``projection_type`` of the Episode projection
#: (DATA_MODEL §5.3; RA §19 lists Relationship and Episode as the two CP4
#: projections of the Phase 4 block). Added by P4-3 — this is the
#: "adding a second type revisits the return shape by design" case the P4-2
#: single-type ensure face recorded (it is ``ensure_projection_jobs`` now).
PROJECTION_TYPE_EPISODE = "EPISODE"

#: The projection types this runtime enqueues and executes, in the order a
#: multi-type face reports them (P4-3: the tuple is now the *set* the ensure
#: face walks, so its order is an interface, not a detail). A job whose type
#: is not here cannot be claimed by any executor, so :meth:`run_pending`
#: rejects it deterministically instead of leaving it pending forever.
SUPPORTED_PROJECTION_TYPES: tuple[str, ...] = (
    PROJECTION_TYPE_RELATIONSHIP,
    PROJECTION_TYPE_EPISODE,
)

#: Digest encoding: canonical fields join with US (ASCII 0x1f, the repo's
#: unit-separator convention) so no field boundary can be forged by content.
SLICE_FIELD_SEPARATOR = "\x1f"

#: Job-id prefix — the ``pj-`` family beside the repo's ``rm-`` (relationship
#: memory) / ``an-`` (analysis) / ``sv-`` (snapshot) deterministic ids.
_JOB_ID_PREFIX = "pj-"

#: Base-version prefix — ``rv-`` for the relationship summary digest.
_BASE_VERSION_PREFIX = "rv-"

#: How many hex characters of the sha256 digest the short ids keep (the
#: repo-wide deterministic-id convention: ``rm-`` / ``an-`` / ``sv-`` ids
#: all keep 20).
_DIGEST_CHARS = 20

#: The two presence markers of the optional fields in :func:`turn_slice_hash`
#: (see its docstring): a missing optional field is the single sentinel
#: ``-``, a present one is its value prefixed with ``+``. The marker keeps
#: "absent" and "present but empty" encodings apart.
_ABSENT_FIELD = "-"
_PRESENT_FIELD = "+"

#: The failure codes that are *deterministic* — the same input will refuse
#: the same way forever, so the job is rejected instead of retried
#: (TASK-…9: "VALIDATION_FAILED / AUTHORITY_VIOLATION / CONFLICT → REJECTED
#: （确定性，不盲重试）"). Everything else (DEPENDENCY_UNAVAILABLE and any
#: later code) is retryable.
_DETERMINISTIC_CODES = frozenset(
    {
        DomainErrorCode.VALIDATION_FAILED,
        DomainErrorCode.AUTHORITY_VIOLATION,
        DomainErrorCode.CONFLICT,
    }
)


def projection_id_for(projection_type: str, turn_id: TurnId) -> ProjectionJobId:
    """The deterministic CP4 job id of one ``(projection_type, turn)`` pair.

    Derived, never minted (P4-0 ④ "stable projection_id"): the encoding is
    ``pj-{sha256(projection_type + US + turn_id).hexdigest()[:20]}``, so a
    re-enqueue after a crash addresses the same durable row and a recovery
    repair can recreate a lost job from its own ids alone — the property the
    crash-gap rule buys.

    ``US`` is :data:`SLICE_FIELD_SEPARATOR` (ASCII 0x1f).

    Precondition (the repo-wide deterministic-id convention, the P4-1
    ``memory_id_for`` included): the caller guarantees that no encoded part
    carries US (0x1f). Both parts are machine-minted today — a fixed type
    word from :data:`SUPPORTED_PROJECTION_TYPES` and a store-minted turn id —
    so no field boundary can be forged in practice; the encoding is a
    convention, not a defence, and does not claim to be one.
    """

    digest = hashlib.sha256(
        f"{projection_type}{SLICE_FIELD_SEPARATOR}{turn_id}".encode("utf-8")
    ).hexdigest()
    return ProjectionJobId(f"{_JOB_ID_PREFIX}{digest[:_DIGEST_CHARS]}")


def _optional_field(value: str | None) -> str:
    """Encode one optional field with its presence marker."""

    if value is None:
        return _ABSENT_FIELD
    return f"{_PRESENT_FIELD}{value}"


def turn_slice_hash(slice_: CanonicalTurnSlice) -> str:
    """The ``source_turn_slice_hash`` of one CanonicalTurnSlice (DATA_MODEL
    §22.1: the hash a projection job was computed from).

    Encoding rule (fixed here, because it is the revalidation contract — the
    same rule must reproduce the same digest for the same slice):

    ``sha256(US.join(parts)).hexdigest()`` over exactly these ten parts, in
    this order — the coordination turn id, the conversation id, the turn
    sequence, the user turn id, the user turn's raw content, the user turn's
    message sequence, and then the four optional assistant-side facts: the
    assistant turn id, its content, its delivery state and the turn outcome.

    Deliberately **not** hashed: every timestamp, and the normalised content
    (the raw utterance is the canonical text; normalisation is a derived
    view). An absent optional field encodes as the single sentinel ``-``, a
    present one as ``+`` followed by its value — so "no assistant turn" and
    "an empty assistant content" never encode alike.

    One consequence worth stating plainly: the digest covers ``raw_content``,
    while the Recorder consumes ``normalized_content or raw_content`` — a
    normaliser version change does not move this hash, so normalisation work
    must be invalidated by its own means (a new projection type / job), never
    by assuming this digest noticed.

    Sequences are encoded as their decimal text; ids and vocabularies as
    their own string form (the same text the durable columns hold).
    """

    assistant = slice_.assistant_turn
    parts = (
        str(slice_.turn_id),
        str(slice_.conversation_id),
        str(int(slice_.turn_sequence)),
        str(slice_.user_turn.user_turn_id),
        slice_.user_turn.raw_content,
        str(int(slice_.user_turn.message_sequence)),
        _optional_field(
            None if assistant is None else str(assistant.assistant_turn_id)
        ),
        _optional_field(None if assistant is None else assistant.content),
        _optional_field(
            None if assistant is None else assistant.delivery_state.value
        ),
        _optional_field(None if slice_.outcome is None else slice_.outcome.value),
    )
    return hashlib.sha256(
        SLICE_FIELD_SEPARATOR.join(parts).encode("utf-8")
    ).hexdigest()


def base_version_for(
    summary: SamePersonaExistingRelationshipSummary,
) -> str:
    """The ``base_domain_version`` of one same-persona relationship summary.

    Derived, never minted: ``rv-{sha256(...)[:20]}`` over the summary's own
    ordered ``(relationship_memory_id, US, status)`` pairs, in the order the
    summary carries them (the store's durable ``ORDER BY created_at,
    relationship_memory_id``). Recomputing it for the unchanged base yields
    the same string, and any change to the base — a new ACTIVE memory, a
    superseded one leaving the summary, a status move — yields a different
    one, which is exactly what the version-aware revalidation needs
    (DATA_MODEL §22.1).

    The summary is already the scope-bound view (one Persona×User pair,
    ACTIVE rows), so the digest is taken over precisely what it carries: the
    scope itself is bound into the read that produced it, never re-derived
    here (DOMAIN_MODEL §17).
    """

    digest = hashlib.sha256(
        SLICE_FIELD_SEPARATOR.join(
            f"{entry.relationship_memory_id}{SLICE_FIELD_SEPARATOR}"
            f"{entry.status.value}"
            for entry in summary.memories
        ).encode("utf-8")
    ).hexdigest()
    return f"{_BASE_VERSION_PREFIX}{digest[:_DIGEST_CHARS]}"


@dataclass(frozen=True)
class ProjectionJobView:
    """The docs/DATA_MODEL.md §22.1 column view of one projection job.

    Field for field the durable ``projection_job`` row: the registry's
    ``projection_id`` is ``projection_job_id`` here, ``base_domain_version``
    is nullable (a job that was never claimed has no base yet), and no
    derived convenience field is added — this is the row, not an
    interpretation of it.
    """

    projection_job_id: ProjectionJobId
    projection_type: str
    source_turn_id: TurnId
    source_turn_slice_hash: str
    base_domain_version: str | None
    status: ProjectionJobState
    attempt_count: int
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ProjectionRunResult:
    """What one pending job did in one run (the run's own trace).

    ``status`` is the job's state *after* this run — COMMITTED for a landed
    projection, REJECTED for a deterministic refusal, FAILED_RETRYABLE for a
    transient one — and ``detail`` is the human-readable why (the committed
    count summary, the refusal reason, or the retryable error).
    """

    projection_job_id: ProjectionJobId
    projection_type: str
    status: ProjectionJobState
    detail: str


@runtime_checkable
class ProjectionTurnSource(Protocol):
    """The narrow durable read face the runtime needs about turns.

    Satisfied structurally by ``SqliteConversationStore`` (the
    ``TurnRecordRecoverySource`` precedent): the runtime package stays
    SQL-free (Gate item 2) while the projection runtime can still reconcile
    a job against the *current* durable turn — its coordination status, its
    canonical slice, and the conversation that owns it.
    """

    def get_turn_record(self, turn_id: TurnId) -> Result[TurnRecordData | None]:
        ...

    def get_canonical_turn_slice(
        self, turn_id: TurnId
    ) -> Result[CanonicalTurnSlice | None]:
        ...

    def get_conversation(
        self, conversation_id: ConversationId
    ) -> Result[ConversationRecord | None]:
        ...


@runtime_checkable
class ProjectionJobStore(Protocol):
    """The durable CP4 work queue (runtime-owned port; the SQLite adapter is
    ``elc.platform.db.projection_store.SqliteProjectionStore``).

    Two vocabularies meet here, and this docstring is the mapping: the
    registry view ``ProjectionJobRecord.source_version`` *is* the durable
    column ``source_turn_slice_hash`` (docs/DOMAIN_MODEL.md §16 registers
    ``source_version``; docs/DATA_MODEL.md §22.1 — and therefore migration
    0002's table — names the column ``source_turn_slice_hash``). The record's
    ``conversation_id`` is registry context: the durable table keys a job by
    its source turn and has no conversation column, so conversation-scoped
    reads join through ``turn_record``.
    """

    def enqueue_projection(
        self, job: ProjectionJobRecord
    ) -> Result[ProjectionJobId]:
        """Make one job durable — idempotently.

        Mapping and replay rules (all three are the P4-0 ④ contract):

        - ``job.source_version`` is written to ``source_turn_slice_hash``;
        - a **new row is born PENDING and only PENDING**: a record carrying
          any other state is refused (VALIDATION_FAILED, nothing written) —
          the §22.1 machine owns every later move, so a caller-declared
          RUNNING / COMMITTED / REJECTED birth would be a row the machine
          never walked (and one that no pending read would ever see again);
        - the **same id with the same payload** (projection type, source
          turn, slice hash) is a replay: ``Ok`` the id and write nothing;
        - the **same id with a different payload** is a ``CONFLICT`` — a
          stable id that would describe a different job is an error, never
          an overwrite (DATA_MODEL §1.2);
        - an existing row's **state is never reset**: its status, attempt
          count and base version are the durable row's own facts, so a
          re-enqueue of a claimed or committed job leaves them exactly where
          they are.
        """
        ...

    def claim_projection(
        self, projection_id: ProjectionJobId, *, base_version: str | None
    ) -> Result[ProjectionJobView]:
        """PENDING / FAILED_RETRYABLE → RUNNING under a status CAS.

        The attempt counter advances and ``base_domain_version`` is written
        to the value the caller just recomputed (the version-aware half of
        the §22.1 retry rule). ``base_domain_version`` is a *snapshot at
        claim time*: execution reads the current base again through the
        executor, so the column is the authorization record, never the
        execution's input. Any other durable state — RUNNING, COMMITTED,
        REJECTED — refuses with ``CONFLICT``: a claimed job is not claimed
        twice, and a terminal job is never re-opened.
        """
        ...

    def complete_projection(
        self, projection_id: ProjectionJobId
    ) -> Result[ProjectionJobView]:
        """RUNNING → COMMITTED (the projection landed). Any other state is a
        ``CONFLICT`` — only a job this run claimed may complete."""
        ...

    def fail_projection(
        self, projection_id: ProjectionJobId
    ) -> Result[ProjectionJobView]:
        """RUNNING → FAILED_RETRYABLE (a transient failure: the job may be
        claimed again). Any other state is a ``CONFLICT``."""
        ...

    def reopen_projection(
        self, projection_id: ProjectionJobId
    ) -> Result[ProjectionJobView]:
        """RUNNING → FAILED_RETRYABLE — the stale-run re-open (§22).

        A RUNNING row whose run never reported is not finished work and must
        not be stranded: the startup scan re-opens it so the ordinary retry
        edge can claim it again (see
        :meth:`CP4ProjectionRuntime.recover_stale_running` for why that is a
        liveness fact, not a guess). Only RUNNING may be re-opened — a
        PENDING / FAILED_RETRYABLE row is already claimable, and a COMMITTED /
        REJECTED row is finished work; any other state is a ``CONFLICT``.
        """
        ...

    def running_projections(
        self,
    ) -> Result[tuple[ProjectionJobView, ...]]:
        """Every RUNNING job, in a deterministic order (the startup scan).

        Deliberately not conversation-scoped: a RUNNING row is global residue
        — it belongs to no conversation's *pending* set — and the startup pass
        is the one place that may look at all of them.
        """
        ...

    def unfinished_projections(
        self,
    ) -> Result[tuple[ProjectionJobView, ...]]:
        """Every unfinished job in the queue (PENDING + FAILED_RETRYABLE), in
        a deterministic order — the whole-registry read.

        The startup sweep drains what is *in the queue*, not only what it just
        repaired or re-opened: a PENDING row left by a crash between its
        enqueue and its run (or a FAILED_RETRYABLE row nobody came back for)
        belongs to a conversation the sweep would otherwise never visit.
        """
        ...

    def reject_projection(
        self, projection_id: ProjectionJobId, *, reason: str
    ) -> Result[ProjectionJobView]:
        """PENDING / RUNNING / FAILED_RETRYABLE → REJECTED (the deterministic
        refusal: this job can never be computed as it stands, so it must
        stop being retried — no blind replay, §22.1).

        ``reason`` is the caller's explanation of the refusal. The §22.1
        column set is closed and this slice adds no migration, so the durable
        row has no reason column: the reason travels back to the caller (its
        run result / run trace), never into the table. COMMITTED and
        REJECTED refuse with ``CONFLICT`` — a landed projection is not
        un-landed by a rejection.
        """
        ...

    def get_projection(
        self, projection_id: ProjectionJobId
    ) -> Result[ProjectionJobView | None]:
        """One durable job row (``None`` = never enqueued). Pure read."""
        ...

    def pending_projections(
        self, conversation_id: ConversationId
    ) -> Result[tuple[ProjectionJobView, ...]]:
        """The conversation's PENDING + FAILED_RETRYABLE jobs, in a
        deterministic order.

        The ``projection_job`` table has no conversation column, so the read
        joins through ``turn_record`` (the job's source turn owns the
        conversation). COMMITTED and REJECTED jobs are finished work and are
        not returned — recovery only ever walks unfinished work
        (RA §22 "只恢复未完成 action/projection").
        """
        ...

    def turns_missing_projection(
        self, projection_type: str
    ) -> Result[tuple[TurnId, ...]]:
        """The COMPLETED turns that have no job of this type, in a
        deterministic order (the crash-gap read).

        "Missing" is a durable fact, computed by an anti-join: a turn that
        completed and never got its job row is exactly the residue a crash
        between the turn's commit points leaves behind, and the deterministic
        id is what lets the repair recreate it.
        """
        ...


@runtime_checkable
class ProjectionExecutor(Protocol):
    """One projection type's execution face (the per-type policy).

    A projection type is a *derived, rebuildable* artifact (RA §26.1 /
    §22.1), so its executor is a pure-ish computation over durable reads:
    it owns what the projection means, the runtime owns when it runs, when
    it is retried and what a failure means.
    """

    @property
    def projection_type(self) -> str:
        """The §22.1 type word this executor serves."""
        ...

    def base_version(self, turn: TurnRecordData) -> Result[str]:
        """The *current* base domain version the projection would build on.

        Recomputed on every run (never read back from the job row): the
        version-aware half of DATA_MODEL §22.1's revalidation rule. A
        refusal with a deterministic code rejects the job; a
        ``DEPENDENCY_UNAVAILABLE``-style refusal leaves it pending for a
        later run.
        """
        ...

    def project(self, view: ProjectionJobView) -> Result[str]:
        """Run the projection for one claimed job.

        The face is deliberately *not* called ``execute``: tests/architecture
        Gate item 2 reserves the ``execute`` / ``commit`` / ``rollback`` call
        vocabulary for the DB machinery ``elc.runtime`` must never touch, and
        ``project()`` both passes that gate and says what it does.

        Returns a short count/summary text on success (kept in the run
        result, never in a durable column) or an ``Err`` whose code decides
        the job's fate: VALIDATION_FAILED / AUTHORITY_VIOLATION / CONFLICT
        reject it (deterministic — never blindly retried), anything else
        makes it FAILED_RETRYABLE.
        """
        ...


class CP4ProjectionRuntime:
    """Executes the CP4 projection queue: ensure, revalidate, run, record.

    Assembled from three injected ports — the durable job store, the
    per-type executors, and a narrow turn source — so the runtime package
    owns the policy while every byte of persistence stays in the platform
    layer (Gate item 2). The class holds no coordinator guard and takes none:
    the caller releases the guard *before* calling in (RA §19/§24.1), which
    the guard-pin test in tests/phase4 asserts from inside an executor.

    **Invariant — the executor set is exactly the supported set** (P4-3,
    review LOW-2; all three shapes are refuse-at-construction, each naming
    the type word it objects to):

    1. every entry of :data:`SUPPORTED_PROJECTION_TYPES` has an executor —
       a *missing* one would have its jobs rejected *terminally*, because the
       ensure face enqueues one job per supported type whatever the executors
       are: the deterministic ids would be spent, and a later, correct
       assembly's ensure would replay them as the same REJECTED rows instead
       of reviving the work;
    2. no type has *two* — otherwise "which one runs" is an accident of
       declaration order, and the answer would differ between a fresh
       assembly and a reordered one;
    3. no executor serves a type outside the supported set — such an
       executor is never enqueued for (no job of that type is ever minted),
       while it *would* silently widen dispatch to any foreign row that
       happens to carry that type word.

    The refusal is a construction-time ``ValueError`` rather than a
    ``Result``: an assembly defect is not a per-job outcome, and every
    ``Result`` this class returns means "about a job". Failing before any row
    exists is the only refusal that leaves the queue recoverable, and raising
    on a programming error is the repo-wide convention (a stale epoch also
    raises).
    """

    def __init__(
        self,
        *,
        store: ProjectionJobStore,
        executors: tuple[ProjectionExecutor, ...],
        turns: ProjectionTurnSource,
    ) -> None:
        self._store = store
        self._executors = tuple(executors)
        _require_complete_executor_set(self._executors)
        self._turns = turns
        #: The jobs *this process* claimed and has not settled yet
        #: (process-local, never durable — see ``recover_stale_running``: a
        #: fresh instance starts empty, which is exactly what makes
        #: cross-process residue recoverable while a live in-process run is
        #: never touched). Entries leave the set through ``_settle`` the
        #: moment a run reports its outcome, so the set tracks live work
        #: rather than every job the process ever claimed (F-5).
        self._claimed_here: set[ProjectionJobId] = set()

    # -- ensure (the enqueue face) -----------------------------------------

    def ensure_projection_jobs(
        self, turn_id: TurnId
    ) -> Result[tuple[ProjectionJobId, ...]]:
        """Ensure the turn's CP4 jobs exist — the crash-gap repair face.

        Reads the durable TurnRecord and the canonical slice, and enqueues
        one job per entry of :data:`SUPPORTED_PROJECTION_TYPES` under its
        deterministic id. Only a ``COMPLETED`` turn is eligible (RA §19
        "默认在 canonical turn 后运行"; a nonterminal or failed turn has no
        canonical outcome to project), and a turn without a canonical slice
        is refused rather than hashed from nothing — both refusals are
        ``VALIDATION_FAILED``, and both write nothing.

        Enqueueing is idempotent through the store, so calling this twice for
        the same turn leaves exactly one row per type.

        **P4-3 signature change** (the revisit the P4-2 single-type shape
        recorded): the return is a *tuple*, one id per supported type, in
        :data:`SUPPORTED_PROJECTION_TYPES` order — the same order the durable
        write below walks. A caller that only wants one type's job must say
        which (``jobs[0]`` is RELATIONSHIP today, which is exactly the
        coupling this face no longer hides). With one type the tuple had one
        element; with two it has two, and every caller has to decide what it
        means to hold "the job" of a multi-type turn.
        """

        return self._ensure_for_turn(turn_id)

    def ensure_missing_jobs(self) -> Result[tuple[ProjectionJobId, ...]]:
        """Repair every crash gap: COMPLETED turns with no job of a
        supported type get theirs, in deterministic order.

        The scan is the durable anti-join (``turns_missing_projection``), one
        pass per supported type. **The repair is per ``(type, turn)`` pair**,
        not per turn: the pass for a type enqueues exactly that type's
        missing ids for the turns the anti-join named, so a turn that already
        has its RELATIONSHIP row but lost its EPISODE row gets the EPISODE row
        back and nothing else is touched. That granularity is what the
        crash-gap rule means once a turn owns more than one job: the *hole*
        is per pair, and repairing it must not re-enqueue a sibling row whose
        payload has since diverged — that row is not a gap, it is the queue's
        own business, and :meth:`run_pending` decides its fate
        (P4-3; pinned by test).

        Nothing is re-derived from a message log (P4-0 ④ crash-gap: the
        deterministic id is what makes this possible).
        """

        ensured: list[ProjectionJobId] = []
        for projection_type in SUPPORTED_PROJECTION_TYPES:
            found = self._store.turns_missing_projection(projection_type)
            if isinstance(found, Err):
                return found
            for turn_id in found.value:
                jobs = self._ensure_for_turn(turn_id, (projection_type,))
                if isinstance(jobs, Err):
                    return jobs
                ensured.extend(jobs.value)
        return Ok(tuple(ensured))

    def _ensure_for_turn(
        self,
        turn_id: TurnId,
        projection_types: tuple[str, ...] = SUPPORTED_PROJECTION_TYPES,
    ) -> Result[tuple[ProjectionJobId, ...]]:
        record_result = self._turns.get_turn_record(turn_id)
        if isinstance(record_result, Err):
            return record_result
        record = record_result.value
        if record is None:
            return _validation(f"turn record not found: {turn_id}")
        if record.status is not TurnStatus.COMPLETED:
            return _validation(
                f"turn {turn_id} is {record.status.value}; a projection job"
                " exists only for a COMPLETED turn (RUNTIME §19: the"
                " projection runs after the canonical turn)"
            )
        slice_result = self._turns.get_canonical_turn_slice(turn_id)
        if isinstance(slice_result, Err):
            return slice_result
        slice_ = slice_result.value
        if slice_ is None:
            return _validation(
                f"canonical turn slice not found: {turn_id} (a projection"
                " needs the slice it would be computed from)"
            )
        source_hash = turn_slice_hash(slice_)
        ids: list[ProjectionJobId] = []
        for projection_type in projection_types:
            job = ProjectionJobRecord(
                projection_job_id=projection_id_for(projection_type, turn_id),
                conversation_id=str(record.conversation_id),
                source_turn_id=turn_id,
                projection_type=projection_type,
                source_version=source_hash,
                state=ProjectionJobState.PENDING,
            )
            enqueued = self._store.enqueue_projection(job)
            if isinstance(enqueued, Err):
                return enqueued
            ids.append(enqueued.value)
        return Ok(tuple(ids))

    # -- run (the execution face) ------------------------------------------

    def run_pending(
        self, conversation_id: ConversationId
    ) -> Result[tuple[ProjectionRunResult, ...]]:
        """Run the conversation's pending jobs, oldest first.

        Every job that can run does run — the durable row is the record, so
        one job's internal failure does not cancel the others; the first
        internal failure still travels back as the ``Err`` (the caller is
        never told the pass succeeded). The per-job rules live in
        ``_run_one``: revalidate ``source_turn_slice_hash`` against the
        *current* slice, recompute the base, claim, execute, and record the
        outcome on the §22.1 machine.
        """

        pending = self._store.pending_projections(conversation_id)
        if isinstance(pending, Err):
            return pending
        results: list[ProjectionRunResult] = []
        failure: DomainError | None = None
        for view in pending.value:
            outcome = self._run_one(view)
            if isinstance(outcome, Ok):
                results.append(outcome.value)
            elif failure is None:
                failure = outcome.error
        if failure is not None:
            return Err(failure)
        return Ok(tuple(results))

    def run_after_turn(
        self, conversation_id: ConversationId, turn_id: TurnId
    ) -> Result[tuple[ProjectionRunResult, ...]]:
        """The post-turn entry: ensure this turn's jobs, then run the
        conversation's pending queue.

        Called by the coordinator *after* the guard is released. Never
        raises: an internal exception (including one thrown by an executor)
        becomes an ``Err`` — the projection line must not be able to travel
        into the turn's own result (R-INV-010; RA §19).

        Both halves always happen, in this order and for these reasons. A
        turn that is not eligible for enqueueing is the *expected* post-turn
        state of a failed turn, so its ``VALIDATION_FAILED`` is not carried
        as a failure while the conversation's pending backlog still gets its
        run; any other enqueue refusal (a deterministic-id clash, a store
        error) is a real one and is reported — after the queue ran, so a bad
        row cannot stop the queue from making progress. The call returns the
        queue's own ``Err`` when the queue failed, and the enqueue refusal
        otherwise: progress and reporting are both required, and silently
        dropping either is not.
        """

        try:
            failure: DomainError | None = None
            ensured = self.ensure_projection_jobs(turn_id)
            if isinstance(ensured, Err) and (
                ensured.error.code is not DomainErrorCode.VALIDATION_FAILED
            ):
                failure = ensured.error
            ran = self.run_pending(conversation_id)
            if isinstance(ran, Err):
                return ran
            if failure is not None:
                return Err(failure)
            return ran
        except Exception as exc:  # noqa: BLE001 — never travel into the turn
            return Err(
                DomainError(
                    code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                    message=(
                        f"projection run failed for conversation"
                        f" {conversation_id}: {exc!r} (a projection failure is"
                        " never the turn's failure — R-INV-010)"
                    ),
                )
            )

    # -- read (the startup mapping face) -----------------------------------

    def job_view(
        self, projection_id: ProjectionJobId
    ) -> Result[ProjectionJobView | None]:
        """One durable job row (pure read; ``None`` = never enqueued).

        The startup sweep needs it because a job id is a *hash*: the
        conversation a crash-gap job belongs to is only recoverable by
        reading the job's source turn back (see the coordinator's
        ``_recover_projections``).
        """

        return self._store.get_projection(projection_id)

    def unfinished_projections(
        self,
    ) -> Result[tuple[ProjectionJobView, ...]]:
        """The whole unfinished backlog (PENDING + FAILED_RETRYABLE), in the
        queue's own order — a pure read.

        The startup sweep needs it because the registry is the ground truth
        of "work that still has to happen": a job the previous process
        enqueued but never ran, or one it failed and left retryable, is in
        the queue — and a sweep that only visited the conversations it had
        just touched would leave that work to a user who may never come back
        to that conversation. The post-turn path stays conversation-scoped
        (that is what ``pending_projections`` is for); this face is the
        startup drain.
        """

        return self._store.unfinished_projections()

    def recover_stale_running(self) -> Result[tuple[ProjectionJobId, ...]]:
        """Re-open the RUNNING residue of a dead process (§22's startup scan).

        Why this is safe *without* inventing TTL / heartbeat machinery
        (Local V1 §24.1: liveness is the ``runtime_epoch``, never a timer) —
        two facts, and the second is now a mechanism rather than a calling
        convention:

        - the scan is a *startup* face, and a freshly constructed runtime has
          claimed nothing, so a RUNNING row visible then was claimed by a
          previous process and never reported back (the crash window between
          claim and completion);
        - this instance skips every projection id in its own
          ``_claimed_here`` set — the jobs *it* claimed and has not finished
          are live work, and the set is process-local, so a restart (an empty
          set) still collects the previous process's residue, while a caller
          who invokes this face mid-process cannot have a live run stolen.
          A job whose run reported (COMMITTED / FAILED_RETRYABLE / REJECTED)
          has already left the set (``_settle``, F-5), so "in the set" means
          "claimed here and still running" — which is exactly the question
          this scan asks.

        Re-opening is not a replay: it only moves the row onto the ordinary
        retry edge, so the next :meth:`run_pending` still revalidates the
        ``source_turn_slice_hash`` and recomputes the base before claiming
        anything (DATA_MODEL §22.1 — no blind replay).
        """

        rows = self._store.running_projections()
        if isinstance(rows, Err):
            return rows
        reopened: list[ProjectionJobId] = []
        for view in rows.value:
            if view.projection_job_id in self._claimed_here:
                continue  # a run this process owns is live, not residue
            outcome = self._store.reopen_projection(view.projection_job_id)
            if isinstance(outcome, Err):
                return outcome
            reopened.append(outcome.value.projection_job_id)
        return Ok(tuple(reopened))

    # -- internals ---------------------------------------------------------

    def _run_one(self, view: ProjectionJobView) -> Result[ProjectionRunResult]:
        executor = self._executor_for(view.projection_type)
        if executor is None:
            return self._reject(
                view,
                f"unsupported projection_type {view.projection_type!r}: no"
                f" executor is registered (SUPPORTED_PROJECTION_TYPES="
                f"{SUPPORTED_PROJECTION_TYPES!r})",
            )

        record_result = self._turns.get_turn_record(view.source_turn_id)
        if isinstance(record_result, Err):
            return record_result
        record = record_result.value
        if record is None:
            return self._reject(
                view, f"source turn not found: {view.source_turn_id}"
            )
        if record.status is not TurnStatus.COMPLETED:
            return self._reject(
                view,
                f"source turn {view.source_turn_id} is"
                f" {record.status.value}, not COMPLETED",
            )

        slice_result = self._turns.get_canonical_turn_slice(view.source_turn_id)
        if isinstance(slice_result, Err):
            return slice_result
        slice_ = slice_result.value
        if slice_ is None:
            return self._reject(
                view,
                f"canonical turn slice not found: {view.source_turn_id}",
            )
        if turn_slice_hash(slice_) != view.source_turn_slice_hash:
            # DATA_MODEL §22.1 source-aware revalidation. The durable slice
            # the job was computed from is not the current one, so replaying
            # the job would project a turn that no longer exists in that
            # form — the one thing the contract forbids ("不允许 blind SQL
            # replay"). A retry would recompute the same mismatch forever,
            # so the refusal is REJECTED, not FAILED_RETRYABLE.
            return self._reject(view, "source_turn_slice_hash changed")

        base = executor.base_version(record)
        if isinstance(base, Err):
            if base.error.code in _DETERMINISTIC_CODES:
                return self._reject(
                    view, f"base version refused: {base.error.message}"
                )
            # Transient: the job stays PENDING (unclaimed) and the queue
            # keeps it for a later run — a transient refusal is not a
            # rejection.
            return Err(base.error)

        claimed = self._store.claim_projection(
            view.projection_job_id, base_version=base.value
        )
        if isinstance(claimed, Err):
            return claimed
        running = claimed.value
        # The claim is this process's own work from here on: remembered so
        # the stale-run scan can tell a live run from a dead one's residue.
        self._claimed_here.add(running.projection_job_id)

        executed = executor.project(running)
        if isinstance(executed, Ok):
            completed = self._store.complete_projection(
                running.projection_job_id
            )
            if isinstance(completed, Err):
                return completed
            # F-5 (DEC-OPI-4d516e4f.13 revisit item three): the run reported,
            # so this process no longer owns the claim — forgetting it here is
            # what keeps the set bounded by the *live* runs instead of by
            # every job the process ever touched.
            self._settle(running.projection_job_id)
            return Ok(
                ProjectionRunResult(
                    projection_job_id=completed.value.projection_job_id,
                    projection_type=completed.value.projection_type,
                    status=completed.value.status,
                    detail=f"committed: {executed.value}",
                )
            )
        if executed.error.code in _DETERMINISTIC_CODES:
            return self._reject(
                running,
                f"deterministic refusal: {executed.error.message}",
            )
        failed = self._store.fail_projection(running.projection_job_id)
        if isinstance(failed, Err):
            return failed
        self._settle(running.projection_job_id)
        return Ok(
            ProjectionRunResult(
                projection_job_id=failed.value.projection_job_id,
                projection_type=failed.value.projection_type,
                status=failed.value.status,
                detail=f"retryable: {executed.error.message}",
            )
        )

    def _reject(
        self, view: ProjectionJobView, reason: str
    ) -> Result[ProjectionRunResult]:
        rejected = self._store.reject_projection(
            view.projection_job_id, reason=reason
        )
        if isinstance(rejected, Err):
            return rejected
        # F-5: a rejected job is finished work, so the claim is settled too.
        self._settle(view.projection_job_id)
        return Ok(
            ProjectionRunResult(
                projection_job_id=rejected.value.projection_job_id,
                projection_type=rejected.value.projection_type,
                status=rejected.value.status,
                detail=reason,
            )
        )

    def _settle(self, projection_id: ProjectionJobId) -> None:
        """Forget a claim this process finished (§F-5).

        Called on every path where the run *reported* an outcome to the
        durable row — committed, failed-retryable, rejected. A run that
        raised (or whose store call failed) does **not** settle: nothing was
        reported, so the RUNNING row is still this process's live work and
        ``recover_stale_running`` must keep treating it that way. Discarding
        an id that is not there is a no-op, so the face is safe from every
        caller.
        """

        self._claimed_here.discard(projection_id)

    def _executor_for(self, projection_type: str) -> ProjectionExecutor | None:
        for executor in self._executors:
            if executor.projection_type == projection_type:
                return executor
        return None


def _require_complete_executor_set(
    executors: tuple[ProjectionExecutor, ...],
) -> None:
    """Enforce the class invariant: the executor set *is* the supported set.

    The rule, in one place, with all three shapes the invariant has (the
    class docstring states them as the contract; this function is the only
    place that decides them):

    - **missing** — a supported type with no executor;
    - **duplicated** — a type with two, which would make "which one runs" an
      accident of declaration order;
    - **unsupported** — an executor for a type outside
      :data:`SUPPORTED_PROJECTION_TYPES`, which is never enqueued for while
      it would widen dispatch to any foreign row carrying that type word.

    Each is a ``ValueError`` naming the type word (and, for the first two,
    the supported set), because the message has to be enough to fix the
    assembly without reading this function.

    Deliberately *not* a ``Result``: every face of this class returns one, so
    a refusal that travels as a value would be indistinguishable from a
    per-job outcome — and this one is not about a job. It is about the
    process, before it touches the queue at all.
    """

    by_type: dict[str, int] = {}
    for executor in executors:
        by_type[executor.projection_type] = (
            by_type.get(executor.projection_type, 0) + 1
        )
    duplicates = sorted(
        type_word for type_word, count in by_type.items() if count > 1
    )
    if duplicates:
        raise ValueError(
            "CP4ProjectionRuntime takes exactly one executor per projection"
            f" type; duplicated: {duplicates!r}"
        )
    missing = [
        type_word
        for type_word in SUPPORTED_PROJECTION_TYPES
        if type_word not in by_type
    ]
    if missing:
        raise ValueError(
            "CP4ProjectionRuntime needs an executor for every supported"
            f" projection type; missing: {missing!r}"
            f" (SUPPORTED_PROJECTION_TYPES={SUPPORTED_PROJECTION_TYPES!r})"
        )
    unknown = sorted(
        type_word
        for type_word in by_type
        if type_word not in SUPPORTED_PROJECTION_TYPES
    )
    if unknown:
        raise ValueError(
            "CP4ProjectionRuntime received executors for unsupported"
            f" projection types: {unknown!r}"
            f" (SUPPORTED_PROJECTION_TYPES={SUPPORTED_PROJECTION_TYPES!r})"
        )


_E = TypeVar("_E")


def _validation(message: str) -> Err[_E]:
    return Err(
        DomainError(code=DomainErrorCode.VALIDATION_FAILED, message=message)
    )
