"""P4-2 ①-④ — the CP4 projection runtime mechanics (TASK-OPI-4d516e4f.9).

The contract this file pins lives in the ``elc.runtime.types`` module
docstring (P4-0 ④) and is executed by ``elc.runtime.projections`` over the
durable queue (``elc.platform.db.projection_store``, migration 0002's
``projection_job``). Four groups, in the order the task book lists them:

① the runtime mechanics — deterministic ids, idempotent enqueue, the five
   §22.1 states (including the illegal moves), the source-aware
   ``source_turn_slice_hash`` revalidation, the retry edge and the
   unsupported-type rejection;
② the guard pin — a probe executor asserts, from *inside* its own body, that
   the coordinator guard is released and no DB transaction is open when the
   projection runs (RA §19/§24.1);
③ the three invariants of a failed projection — transcript untouched,
   assistant not re-sent, next turn still REPLIED_FULL (R-INV-010);
④ the crash gap — a COMPLETED turn whose job row is missing is repaired from
   the deterministic id, idempotently, and runs to COMMITTED.

Everything runs against the real stores over a fresh in-memory app.db; the
"scripted executor" is the test-side probe for the per-type policy, and the
real RELATIONSHIP executor is exercised in
``test_p4_2_relationship_projection``.
"""

from __future__ import annotations

import hashlib
import sqlite3

import pytest

from elc.conversation import SqliteConversationStore
from elc.learning.store import SqliteLearningStore
from elc.persona import ScriptedPersonaProvider
from elc.platform.db.decision_cycle_store import SqliteDecisionCycleStore
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.db.projection_store import SqliteProjectionStore
from elc.platform.types import (
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    ProjectionJobId,
    Result,
    TurnId,
)
from elc.runtime.controller import ConversationCoordinator
from elc.runtime.projections import (
    PROJECTION_TYPE_EPISODE,
    PROJECTION_TYPE_RELATIONSHIP,
    SUPPORTED_PROJECTION_TYPES,
    CP4ProjectionRuntime,
    ProjectionExecutor,
    ProjectionJobView,
    ProjectionRunResult,
    ProjectionTurnSource,
    base_version_for,
    projection_id_for,
    turn_slice_hash,
)
from elc.runtime.types import (
    ProjectionJobRecord,
    ProjectionJobState,
    TurnRecordData,
)
from elc.teaching.controller import TeachingController
from elc.teaching.targets import TeachingTargetProvider
from tests.conftest import AssemblyGenerationStore
from tests.phase3.conftest import make_lease, make_teaching_coordinator

from .conftest import (
    CONV,
    PERSONA_A,
    REL_USER,
    NoopProjectionExecutor,
    commit_chat_turn,
    complete_executors,
    deliver_reply,
    memory_proposal,
    open_conversation_for,
    projection_job_row,
    projection_job_rows,
    speak,
    turn_slice,
)

JOB = ProjectionJobId("pj-probe")
SLICE_HASH = "slice-hash-1"


# -- probes ----------------------------------------------------------------


class _ScriptedExecutor:
    """The per-type executor a test scripts: the runtime's dispatch target.

    It is a *probe*, not a fake store: it observes the world at the moment
    the runtime runs it (guard held? transaction open?) and answers with the
    outcome the test asked for.
    """

    projection_type = PROJECTION_TYPE_RELATIONSHIP

    def __init__(self, *, base: str = "rv-probe") -> None:
        self.base = base
        self.calls = 0
        self.failure: DomainError | None = None
        self.explode = False
        self.lease_held: bool | None = None
        self.in_transaction: bool | None = None
        self._observer: tuple[object, object, object] | None = None

    def observe(self, lease: object, conn: object, conversation: object) -> None:
        """Remember the guard/transaction/connection to look at from inside
        :meth:`project` (the group-② pin)."""

        self._observer = (lease, conn, conversation)

    def base_version(self, turn: TurnRecordData) -> Result[str]:
        del turn
        return Ok(self.base)

    def project(self, view: ProjectionJobView) -> Result[str]:
        self.calls += 1
        del view
        if self._observer is not None:
            lease, conn, conversation = self._observer
            self.lease_held = lease.is_held(conversation)  # type: ignore[attr-defined]
            self.in_transaction = bool(conn.in_transaction)  # type: ignore[attr-defined]
        if self.explode:
            raise RuntimeError("executor exploded (injected)")
        if self.failure is not None:
            return Err(self.failure)
        return Ok("probe")


def _job(
    *,
    job_id: ProjectionJobId = JOB,
    turn_id: TurnId = TurnId("turn-probe"),
    projection_type: str = PROJECTION_TYPE_RELATIONSHIP,
    source_version: str = SLICE_HASH,
    state: ProjectionJobState = ProjectionJobState.PENDING,
) -> ProjectionJobRecord:
    return ProjectionJobRecord(
        projection_job_id=job_id,
        conversation_id="conv-probe",
        source_turn_id=turn_id,
        projection_type=projection_type,
        source_version=source_version,
        state=state,
    )


def _runtime(
    store: SqliteProjectionStore,
    turns: ProjectionTurnSource,
    *executors: ProjectionExecutor,
) -> CP4ProjectionRuntime:
    """A runtime over the given executors, completed with a no-op per
    supported type they do not cover.

    P4-3 (review LOW-2) semantic sync: a complete executor set is now a
    construction requirement, so a probe that scripts one type must supply
    the other. The fillers never fail and are never asserted on, so every
    scenario below (and every ``_runs_of`` selection) keeps its meaning.
    """

    return CP4ProjectionRuntime(
        store=store, executors=complete_executors(*executors), turns=turns
    )


def _runs_of(
    runs: Result[tuple[ProjectionRunResult, ...]],
    projection_type: str = PROJECTION_TYPE_RELATIONSHIP,
) -> list[ProjectionRunResult]:
    """The run results of one projection type (P4-3 semantic sync).

    The ensure face now enqueues one job per entry of
    ``SUPPORTED_PROJECTION_TYPES``, so a run reports both types. These pins
    are about the RELATIONSHIP executor (the scripted probe below serves
    that type), and selecting by type keeps each assertion about what it was
    about — the queue orders by ``created_at, projection_id``, which puts no
    fixed order on the types.
    """

    assert isinstance(runs, Ok), runs
    return [item for item in runs.value if item.projection_type == projection_type]


def _assistant_rows(db: sqlite3.Connection) -> list[tuple[object, ...]]:
    return [
        tuple(row)
        for row in db.execute(
            "SELECT assistant_turn_id, content FROM assistant_turn"
            " ORDER BY message_sequence"
        ).fetchall()
    ]


def _projecting_coordinator(
    *,
    store: SqliteConversationStore,
    generation_store: AssemblyGenerationStore,
    fence: RuntimeEpochFence,
    learning: SqliteLearningStore,
    decision_cycle_store: SqliteDecisionCycleStore,
    teaching_controller: TeachingController,
    target_provider: TeachingTargetProvider,
    runtime: CP4ProjectionRuntime,
) -> ConversationCoordinator:
    """The P3-1A assembly with the probe runtime injected (one helper, so the
    group-②/③ tests state their wiring once)."""

    return make_teaching_coordinator(
        store,
        generation_store,
        make_lease(fence),
        ScriptedPersonaProvider(),
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
        projections=runtime,
    )


# -- ① derived ids and digests ---------------------------------------------


def test_the_projection_id_is_derived_and_deterministic() -> None:
    first = projection_id_for(PROJECTION_TYPE_RELATIONSHIP, TurnId("turn-1"))
    assert first == projection_id_for(PROJECTION_TYPE_RELATIONSHIP, TurnId("turn-1"))
    assert first.startswith("pj-")
    assert first == "pj-" + hashlib.sha256(
        "RELATIONSHIP\x1fturn-1".encode("utf-8")
    ).hexdigest()[:20]
    # A different turn, or a different type, is a different job — both
    # inputs are part of the id.
    assert first != projection_id_for(
        PROJECTION_TYPE_RELATIONSHIP, TurnId("turn-2")
    )
    assert first != projection_id_for("EPISODE", TurnId("turn-1"))


def test_the_slice_hash_tracks_exactly_the_canonical_slice(
    store: SqliteConversationStore,
) -> None:
    conversation = open_conversation_for(store, "conv-hash", PERSONA_A)
    turn_id = speak(store, conversation, "cm-hash-1", "I live in Berlin.")
    bare = turn_slice(store, turn_id)

    # The same durable slice reproduces the same digest.
    assert turn_slice_hash(bare) == turn_slice_hash(turn_slice(store, turn_id))

    # The delivered assistant side changes it (the optional-field encoding),
    # and the digest differs from the no-assistant shape.
    deliver_reply(store, turn_id, conversation, "What do you grow?")
    delivered = turn_slice(store, turn_id)
    assert delivered.assistant_turn is not None
    assert turn_slice_hash(delivered) != turn_slice_hash(bare)

    # The canonical user utterance is part of it.
    other = speak(store, conversation, "cm-hash-2", "I live in Hamburg.")
    assert turn_slice_hash(turn_slice(store, other)) != turn_slice_hash(bare)


def test_the_base_version_changes_when_the_base_changes(
    store: SqliteConversationStore,
    relationship_controller,
) -> None:
    empty = relationship_controller.get_existing_summary(PERSONA_A, REL_USER)
    assert isinstance(empty, Ok)
    version = base_version_for(empty.value)
    assert version.startswith("rv-")
    assert version == base_version_for(empty.value)

    conversation = open_conversation_for(store, "conv-base", PERSONA_A)
    turn_id = speak(store, conversation, "cm-base-1", "I live in Berlin.")
    written = relationship_controller.propose_memory(
        memory_proposal("The user lives in Berlin.", source_turn_id=turn_id)
    )
    assert isinstance(written, Ok)

    moved = relationship_controller.get_existing_summary(PERSONA_A, REL_USER)
    assert isinstance(moved, Ok)
    assert base_version_for(moved.value) != version
    # The same base still reproduces the same version (it is a function of
    # the summary, not of the moment it was read).
    assert base_version_for(moved.value) == base_version_for(
        relationship_controller.get_existing_summary(
            PERSONA_A, REL_USER
        ).value  # type: ignore[union-attr]
    )


def test_the_real_stores_satisfy_the_runtime_ports(
    store: SqliteConversationStore,
    projection_store: SqliteProjectionStore,
    projection_runtime: CP4ProjectionRuntime,
    relationship_projection,
) -> None:
    """The seams are real, not aspirational: the durable store *is* the
    ``ProjectionJobStore``, the conversation store *is* the
    ``ProjectionTurnSource``, and the RELATIONSHIP executor *is* a
    ``ProjectionExecutor`` (the ``TurnRecordRecoverySource`` precedent)."""

    from elc.runtime.projections import (
        ProjectionJobStore,
        ProjectionTurnSource,
    )

    assert isinstance(projection_store, ProjectionJobStore)
    assert isinstance(store, ProjectionTurnSource)
    assert isinstance(relationship_projection, ProjectionExecutor)
    assert projection_runtime is not None


def test_the_runtime_refuses_an_incomplete_executor_set(
    store: SqliteConversationStore,
    projection_store: SqliteProjectionStore,
) -> None:
    """P4-3 (review LOW-2): the ensure face enqueues one job per supported
    type whatever the executors are, so a missing executor would have its
    jobs rejected *terminally* — the deterministic ids spent, and a later
    correct assembly replaying them as the same REJECTED rows. The refusal is
    therefore construction-time, and it names what is missing."""

    with pytest.raises(ValueError) as raised:
        CP4ProjectionRuntime(
            store=projection_store,
            executors=(_ScriptedExecutor(),),  # RELATIONSHIP only
            turns=store,
        )
    message = str(raised.value)
    assert "missing" in message
    for type_word in SUPPORTED_PROJECTION_TYPES:
        if type_word != PROJECTION_TYPE_RELATIONSHIP:
            assert type_word in message
    # The other direction: an assembly with one executor is incomplete only
    # if a supported type is unserved — the complete set constructs fine
    # (the fixture at the top of this file is the positive control).
    assert isinstance(
        _runtime(projection_store, store, _ScriptedExecutor()),
        CP4ProjectionRuntime,
    )


def test_the_runtime_refuses_a_duplicated_executor(
    store: SqliteConversationStore,
    projection_store: SqliteProjectionStore,
) -> None:
    """Two executors for one type would make "which one runs" an accident of
    declaration order — refused, with the type word named."""

    with pytest.raises(ValueError) as raised:
        CP4ProjectionRuntime(
            store=projection_store,
            executors=(_ScriptedExecutor(), _ScriptedExecutor()),
            turns=store,
        )
    message = str(raised.value)
    assert "duplicated" in message
    assert PROJECTION_TYPE_RELATIONSHIP in message


def test_the_runtime_refuses_an_executor_for_an_unsupported_type(
    store: SqliteConversationStore,
    projection_store: SqliteProjectionStore,
) -> None:
    """The rule's other edge (P4-3): an executor for a type the runtime does
    not support would never be enqueued for — and would silently widen the
    dispatch surface to any foreign row that happens to carry that type
    word. Refused rather than carried."""

    with pytest.raises(ValueError) as raised:
        CP4ProjectionRuntime(
            store=projection_store,
            executors=complete_executors(NoopProjectionExecutor("PLANNING_LEDGER")),
            turns=store,
        )
    message = str(raised.value)
    assert "unsupported" in message
    assert "PLANNING_LEDGER" in message


@pytest.mark.parametrize(
    "state",
    [
        ProjectionJobState.RUNNING,
        ProjectionJobState.COMMITTED,
        ProjectionJobState.FAILED_RETRYABLE,
        ProjectionJobState.REJECTED,
    ],
)
def test_a_new_row_is_born_pending_and_nothing_else(
    db: sqlite3.Connection,
    projection_store: SqliteProjectionStore,
    state: ProjectionJobState,
) -> None:
    """F-1: the state machine owns every move after birth. A caller-declared
    non-PENDING birth is refused with zero writes — otherwise a born
    COMMITTED / REJECTED row would be invisible to every pending read for
    good, and a born RUNNING row would claim machine work nobody did."""

    refused = projection_store.enqueue_projection(_job(state=state))
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "born PENDING" in refused.error.message
    assert projection_job_rows(db) == []


def test_the_real_enqueue_path_still_writes_pending_rows(
    db: sqlite3.Connection,
    projection_store: SqliteProjectionStore,
    projection_runtime: CP4ProjectionRuntime,
    coordinator: ConversationCoordinator,
) -> None:
    """F-1 positive control: every real producer (the runtime's ensure face
    and the durable queue's own PENDING records) is untouched."""

    turn = commit_chat_turn(coordinator, "cm-born", "I live in Berlin.", 1)
    ensured = projection_runtime.ensure_projection_jobs(turn.turn_id)
    # P4-3 semantic sync: the ensure face returns one id per supported type,
    # in SUPPORTED_PROJECTION_TYPES order — index 0 is RELATIONSHIP (the
    # older of the two, and the one this pin has always been about).
    assert isinstance(ensured, Ok)
    assert len(ensured.value) == len(SUPPORTED_PROJECTION_TYPES)
    assert projection_job_row(db, ensured.value[0])[5] == "PENDING"
    assert isinstance(projection_store.enqueue_projection(_job()), Ok)
    assert projection_job_row(db, JOB)[5] == "PENDING"


# -- ① idempotent enqueue ---------------------------------------------------


def test_enqueue_replays_identical_payloads_and_refuses_others(
    db: sqlite3.Connection, projection_store: SqliteProjectionStore
) -> None:
    job = _job()
    first = projection_store.enqueue_projection(job)
    assert isinstance(first, Ok) and first.value == JOB
    row = projection_job_row(db, JOB)
    assert row[5] == "PENDING" and row[6] == 0

    # Same id, same payload: a replay — Ok, zero writes.
    replay = projection_store.enqueue_projection(_job())
    assert isinstance(replay, Ok) and replay.value == JOB
    assert projection_job_rows(db) == [row]

    # Same id, different payload: a conflict, never an overwrite.
    conflicted = projection_store.enqueue_projection(
        _job(source_version="slice-hash-2")
    )
    assert isinstance(conflicted, Err)
    assert conflicted.error.code is DomainErrorCode.CONFLICT
    assert projection_job_rows(db) == [row]


def test_enqueue_never_resets_a_claimed_job(
    db: sqlite3.Connection, projection_store: SqliteProjectionStore
) -> None:
    assert isinstance(projection_store.enqueue_projection(_job()), Ok)
    claimed = projection_store.claim_projection(JOB, base_version="rv-1")
    assert isinstance(claimed, Ok)
    assert claimed.value.status is ProjectionJobState.RUNNING
    assert claimed.value.attempt_count == 1
    assert claimed.value.base_domain_version == "rv-1"

    replay = projection_store.enqueue_projection(_job())
    assert isinstance(replay, Ok)
    row = projection_job_row(db, JOB)
    assert row[5] == "RUNNING"  # the durable state is the row's own fact
    assert row[6] == 1
    assert row[4] == "rv-1"


# -- ① the five-state machine ----------------------------------------------


def test_the_state_machine_only_walks_the_legal_edges(
    projection_store: SqliteProjectionStore,
) -> None:
    assert isinstance(projection_store.enqueue_projection(_job()), Ok)

    # From PENDING the only exits are RUNNING and REJECTED.
    premature = projection_store.complete_projection(JOB)
    assert isinstance(premature, Err)
    assert premature.error.code is DomainErrorCode.CONFLICT
    assert "PENDING" in premature.error.message

    claimed = projection_store.claim_projection(JOB, base_version="rv-1")
    assert isinstance(claimed, Ok)
    # A claimed job is not claimed twice.
    assert isinstance(
        projection_store.claim_projection(JOB, base_version="rv-2"), Err
    )

    completed = projection_store.complete_projection(JOB)
    assert isinstance(completed, Ok)
    assert completed.value.status is ProjectionJobState.COMMITTED

    # COMMITTED is finished work: no re-claim, no second completion, and a
    # rejection cannot un-land it.
    assert isinstance(
        projection_store.claim_projection(JOB, base_version="x"), Err
    )
    assert isinstance(projection_store.complete_projection(JOB), Err)
    rejected = projection_store.reject_projection(JOB, reason="late")
    assert isinstance(rejected, Err)
    assert rejected.error.code is DomainErrorCode.CONFLICT


@pytest.mark.parametrize("path", ["pending", "running", "failed_retryable"])
def test_rejection_is_legal_from_every_unfinished_state(
    db: sqlite3.Connection,
    projection_store: SqliteProjectionStore,
    path: str,
) -> None:
    job_id = ProjectionJobId(f"pj-reject-{path}")
    assert isinstance(
        projection_store.enqueue_projection(_job(job_id=job_id)), Ok
    )
    if path in ("running", "failed_retryable"):
        assert isinstance(
            projection_store.claim_projection(job_id, base_version="rv-1"), Ok
        )
    if path == "failed_retryable":
        assert isinstance(projection_store.fail_projection(job_id), Ok)
    rejected = projection_store.reject_projection(job_id, reason="deterministic")
    assert isinstance(rejected, Ok)
    assert rejected.value.status is ProjectionJobState.REJECTED
    assert projection_job_row(db, job_id)[5] == "REJECTED"
    # The counter counts attempts, never rejections.
    assert projection_job_row(db, job_id)[6] == (0 if path == "pending" else 1)


def test_a_retry_recomputes_the_base_and_advances_the_attempt_counter(
    db: sqlite3.Connection, projection_store: SqliteProjectionStore
) -> None:
    assert isinstance(projection_store.enqueue_projection(_job()), Ok)
    assert isinstance(
        projection_store.claim_projection(JOB, base_version="rv-1"), Ok
    )
    failed = projection_store.fail_projection(JOB)
    assert isinstance(failed, Ok)
    assert failed.value.status is ProjectionJobState.FAILED_RETRYABLE

    retried = projection_store.claim_projection(JOB, base_version="rv-2")
    assert isinstance(retried, Ok)
    assert retried.value.attempt_count == 2
    assert retried.value.base_domain_version == "rv-2"
    assert isinstance(projection_store.complete_projection(JOB), Ok)
    assert projection_job_row(db, JOB)[6] == 2


# -- ① source-aware revalidation and the run faces --------------------------


def test_a_moved_slice_is_rejected_and_never_blindly_replayed(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    projection_store: SqliteProjectionStore,
    coordinator: ConversationCoordinator,
) -> None:
    """DATA_MODEL §22.1's source-aware revalidation: the durable row records
    a ``source_turn_slice_hash`` the current slice no longer produces, so the
    job is rejected — claimed by nobody, executed by nobody."""

    executor = _ScriptedExecutor()
    runtime = _runtime(projection_store, store, executor)
    turn = commit_chat_turn(coordinator, "cm-moved", "I live in Berlin.", 1)

    stale = projection_store.enqueue_projection(
        _job(
            job_id=projection_id_for(PROJECTION_TYPE_RELATIONSHIP, turn.turn_id),
            turn_id=turn.turn_id,
            source_version="a-hash-the-slice-no-longer-has",
        )
    )
    assert isinstance(stale, Ok)

    runs = runtime.run_pending(CONV)
    assert isinstance(runs, Ok), runs
    assert [item.status.value for item in runs.value] == ["REJECTED"]
    assert runs.value[0].detail == "source_turn_slice_hash changed"
    # No blind replay: the executor was never called with the stale row.
    assert executor.calls == 0
    row = projection_job_row(db, stale.value)
    assert row[5] == "REJECTED"
    assert row[6] == 0  # never claimed
    assert row[4] is None  # no base was ever computed for it


def test_run_after_turn_commits_the_current_slice(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    projection_store: SqliteProjectionStore,
    coordinator: ConversationCoordinator,
) -> None:
    executor = _ScriptedExecutor(base="rv-current")
    runtime = _runtime(projection_store, store, executor)
    turn = commit_chat_turn(coordinator, "cm-commit", "I live in Berlin.", 1)

    runs = runtime.run_after_turn(CONV, turn.turn_id)
    assert [item.status.value for item in _runs_of(runs)] == ["COMMITTED"]
    assert _runs_of(runs)[0].projection_job_id == projection_id_for(
        PROJECTION_TYPE_RELATIONSHIP, turn.turn_id
    )
    assert _runs_of(runs)[0].detail == "committed: probe"
    assert executor.calls == 1
    row = projection_job_row(db, _runs_of(runs)[0].projection_job_id)
    assert row[4] == "rv-current"  # the base this run recomputed
    assert row[5] == "COMMITTED"
    assert row[6] == 1


def test_a_transient_failure_leaves_the_job_retryable_and_a_retry_lands_it(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    projection_store: SqliteProjectionStore,
    coordinator: ConversationCoordinator,
) -> None:
    executor = _ScriptedExecutor(base="rv-1")
    runtime = _runtime(projection_store, store, executor)
    turn = commit_chat_turn(coordinator, "cm-retry", "I live in Berlin.", 1)

    executor.failure = DomainError(
        code=DomainErrorCode.DEPENDENCY_UNAVAILABLE, message="store offline"
    )
    runs = runtime.run_after_turn(CONV, turn.turn_id)
    assert [item.status.value for item in _runs_of(runs)] == ["FAILED_RETRYABLE"]
    assert _runs_of(runs)[0].detail.startswith("retryable:")
    job_id = _runs_of(runs)[0].projection_job_id
    assert projection_job_row(db, job_id)[5] == "FAILED_RETRYABLE"

    # The retry recomputes the base — a moved base updates the durable
    # column — and lands the projection.
    executor.failure = None
    executor.base = "rv-2"
    retried = runtime.run_after_turn(CONV, turn.turn_id)
    assert [item.status.value for item in _runs_of(retried)] == ["COMMITTED"]
    row = projection_job_row(db, job_id)
    assert row[4] == "rv-2"
    assert row[5] == "COMMITTED"
    assert row[6] == 2
    # The queue is empty afterwards: committed work is not re-run.
    assert runtime.run_pending(CONV).value == ()  # type: ignore[union-attr]


def test_a_deterministic_executor_refusal_rejects_the_job(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    projection_store: SqliteProjectionStore,
    coordinator: ConversationCoordinator,
) -> None:
    executor = _ScriptedExecutor()
    executor.failure = DomainError(
        code=DomainErrorCode.VALIDATION_FAILED, message="scope refused"
    )
    runtime = _runtime(projection_store, store, executor)
    turn = commit_chat_turn(coordinator, "cm-deterministic", "I live in Berlin.", 1)

    runs = runtime.run_after_turn(CONV, turn.turn_id)
    assert [item.status.value for item in _runs_of(runs)] == ["REJECTED"]
    assert _runs_of(runs)[0].detail == "deterministic refusal: scope refused"
    job_id = projection_id_for(PROJECTION_TYPE_RELATIONSHIP, turn.turn_id)
    assert projection_job_row(db, job_id)[5] == "REJECTED"


def test_an_unsupported_type_is_rejected_not_retried_forever(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    projection_store: SqliteProjectionStore,
    coordinator: ConversationCoordinator,
) -> None:
    """P4-3 semantic sync: the foreign type word was ``EPISODE`` while that
    type had no executor here; it is supported now (and every supported type
    must have an executor, review LOW-2), so the pin names a type the runtime
    genuinely does not implement — ``PLANNING_LEDGER``, one of the CP4
    families RA §CP4 lists and this slice has not built. The rule under test
    is unchanged: a foreign row is rejected deterministically, never retried
    forever."""

    runtime = _runtime(projection_store, store, _ScriptedExecutor())
    turn = commit_chat_turn(coordinator, "cm-unsupported", "I live in Berlin.", 1)
    foreign = ProjectionJobId("pj-foreign")
    assert isinstance(
        projection_store.enqueue_projection(
            _job(
                job_id=foreign,
                turn_id=turn.turn_id,
                projection_type="PLANNING_LEDGER",
                source_version=turn_slice_hash(turn_slice(store, turn.turn_id)),
            )
        ),
        Ok,
    )
    runs = runtime.run_pending(CONV)
    assert isinstance(runs, Ok), runs
    rejected = [item for item in runs.value if item.projection_job_id == foreign]
    assert [item.status.value for item in rejected] == ["REJECTED"]
    assert "unsupported projection_type" in rejected[0].detail
    assert projection_job_row(db, foreign)[5] == "REJECTED"


def test_ensure_refuses_a_turn_that_never_completed(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    projection_runtime: CP4ProjectionRuntime,
    conversation,
) -> None:
    del conversation
    turn_id = speak(store, CONV, "cm-nonterminal", "I live in Berlin.")
    # P4-3 semantic sync: the ensure face is plural now (one id per supported
    # type); this pin is about the refusal itself, which happens before any
    # type is walked.
    refused = projection_runtime.ensure_projection_jobs(turn_id)
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "COMPLETED" in refused.error.message
    assert projection_job_rows(db) == []


def test_run_after_turn_does_not_raise_for_an_ineligible_turn(
    store: SqliteConversationStore,
    projection_runtime: CP4ProjectionRuntime,
    conversation,
) -> None:
    del conversation
    turn_id = speak(store, CONV, "cm-ineligible", "I live in Berlin.")
    outcome = projection_runtime.run_after_turn(CONV, turn_id)
    assert isinstance(outcome, Ok)
    assert outcome.value == ()


# -- ② the guard pin --------------------------------------------------------


def test_projections_run_with_the_guard_released_and_no_transaction_open(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    projection_store: SqliteProjectionStore,
    generation_store: AssemblyGenerationStore,
    fence: RuntimeEpochFence,
    learning: SqliteLearningStore,
    decision_cycle_store: SqliteDecisionCycleStore,
    teaching_controller: TeachingController,
    target_provider: TeachingTargetProvider,
    conversation,
) -> None:
    del conversation
    lease = make_lease(fence)
    probe = _ScriptedExecutor()
    probe.observe(lease, db, CONV)
    runtime = _runtime(projection_store, store, probe)
    coordinator = _projecting_coordinator(
        store=store,
        generation_store=generation_store,
        fence=fence,
        learning=learning,
        decision_cycle_store=decision_cycle_store,
        teaching_controller=teaching_controller,
        target_provider=target_provider,
        runtime=runtime,
    )

    turn = commit_chat_turn(coordinator, "cm-guard", "I live in Berlin.", 1)
    assert turn.outcome == "REPLIED_FULL"
    assert probe.calls == 1
    # The pin: RA §19/§24.1 — CP4 runs neither inside the guard nor inside a
    # DB transaction (R-INV-004).
    assert probe.lease_held is False
    assert probe.in_transaction is False
    # The probe is not vacuous: the guard really blocks while held.
    with lease.hold(CONV):
        assert lease.is_held(CONV) is True
    assert lease.is_held(CONV) is False


# -- ③ failure is not the turn's failure -----------------------------------


def test_a_failing_projection_leaves_the_transcript_and_the_next_turn_alone(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    projection_store: SqliteProjectionStore,
    generation_store: AssemblyGenerationStore,
    fence: RuntimeEpochFence,
    learning: SqliteLearningStore,
    decision_cycle_store: SqliteDecisionCycleStore,
    teaching_controller: TeachingController,
    target_provider: TeachingTargetProvider,
    conversation,
) -> None:
    del conversation
    executor = _ScriptedExecutor()
    executor.failure = DomainError(
        code=DomainErrorCode.DEPENDENCY_UNAVAILABLE, message="store offline"
    )
    runtime = _runtime(projection_store, store, executor)
    coordinator = _projecting_coordinator(
        store=store,
        generation_store=generation_store,
        fence=fence,
        learning=learning,
        decision_cycle_store=decision_cycle_store,
        teaching_controller=teaching_controller,
        target_provider=target_provider,
        runtime=runtime,
    )

    turn = commit_chat_turn(coordinator, "cm-inv", "I live in Berlin.", 1)
    # The turn itself still succeeded (a projection failure is not the turn's
    # failure — R-INV-010).
    assert turn.outcome == "REPLIED_FULL"
    assert turn.turn_status.value == "COMPLETED"

    # ① the transcript is unchanged: the canonical slice still carries the
    #    real utterance and its delivered assistant turn.
    slice_ = turn_slice(store, turn.turn_id)
    assert slice_.user_turn.raw_content == "I live in Berlin."
    assert slice_.assistant_turn is not None
    assert slice_.assistant_turn.content == turn.reply_text
    rows_before = _assistant_rows(db)
    assert len(rows_before) == 1

    # The failure is durable, not lost: the job waits as FAILED_RETRYABLE.
    job_id = projection_id_for(PROJECTION_TYPE_RELATIONSHIP, turn.turn_id)
    assert projection_job_row(db, job_id)[5] == "FAILED_RETRYABLE"

    # ② the assistant message is not re-sent: no second canonical row and no
    #    rewritten content.
    assert _assistant_rows(db) == rows_before

    # ③ the next turn is still Ok and replies fully — one more assistant
    #    row, nothing replayed.
    following = commit_chat_turn(coordinator, "cm-inv-2", "Anyway, hello.", 2)
    assert following.outcome == "REPLIED_FULL"
    assert following.turn_status.value == "COMPLETED"
    assert len(_assistant_rows(db)) == 2
    assert turn_slice(store, following.turn_id).user_turn.raw_content == (
        "Anyway, hello."
    )


def test_a_raising_executor_never_travels_into_the_turn(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    projection_store: SqliteProjectionStore,
    generation_store: AssemblyGenerationStore,
    fence: RuntimeEpochFence,
    learning: SqliteLearningStore,
    decision_cycle_store: SqliteDecisionCycleStore,
    teaching_controller: TeachingController,
    target_provider: TeachingTargetProvider,
    conversation,
) -> None:
    del conversation
    executor = _ScriptedExecutor()
    executor.explode = True
    runtime = _runtime(projection_store, store, executor)
    coordinator = _projecting_coordinator(
        store=store,
        generation_store=generation_store,
        fence=fence,
        learning=learning,
        decision_cycle_store=decision_cycle_store,
        teaching_controller=teaching_controller,
        target_provider=target_provider,
        runtime=runtime,
    )

    turn = commit_chat_turn(coordinator, "cm-boom", "I live in Berlin.", 1)
    assert turn.outcome == "REPLIED_FULL"
    assert len(_assistant_rows(db)) == 1
    # run_after_turn turns the exception into an Err (never a raise), so the
    # coordinator drops it. The durable trace is honest: the run started and
    # never reported, which is the same residue a process crash would leave
    # (a stale-RUNNING reclaim policy is deliberately not invented here —
    # this slice's pending face covers PENDING / FAILED_RETRYABLE).
    job_id = projection_id_for(PROJECTION_TYPE_RELATIONSHIP, turn.turn_id)
    assert projection_job_row(db, job_id)[5] == "RUNNING"
    assert isinstance(runtime.run_after_turn(CONV, turn.turn_id), Ok)


# -- F-5: a live in-process run is never stale residue ----------------------


def test_a_run_this_process_claimed_is_not_stale_residue(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    projection_store: SqliteProjectionStore,
    coordinator: ConversationCoordinator,
) -> None:
    """F-5: the runtime remembers the jobs it claimed. A RUNNING row this
    process owns is live work — the stale-run scan must not re-open it, no
    matter who calls the face."""

    executor = _ScriptedExecutor()
    executor.explode = True  # the run starts and never reports
    runtime = _runtime(projection_store, store, executor)
    turn = commit_chat_turn(coordinator, "cm-inprocess", "I live in Berlin.", 1)
    crashed = runtime.run_after_turn(CONV, turn.turn_id)
    assert isinstance(crashed, Err)  # trapped, never raised
    assert crashed.error.code is DomainErrorCode.DEPENDENCY_UNAVAILABLE
    job_id = projection_id_for(PROJECTION_TYPE_RELATIONSHIP, turn.turn_id)
    assert projection_job_row(db, job_id)[5] == "RUNNING"

    reopened = runtime.recover_stale_running()
    assert isinstance(reopened, Ok)
    assert reopened.value == ()
    assert projection_job_row(db, job_id)[5] == "RUNNING"  # untouched
    assert projection_job_row(db, job_id)[6] == 1


def test_a_settled_run_leaves_the_live_claim_set(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    projection_store: SqliteProjectionStore,
    coordinator: ConversationCoordinator,
) -> None:
    """F-5's third face (P4-3, DEC-OPI-4d516e4f.13 revisit item three): the
    claim set tracks *live* work, not every job the process ever touched.

    A run that **reported** an outcome — committed, failed-retryable,
    rejected — leaves the set, so it cannot grow without bound over a long
    process; a run that *raised* does not, which is what keeps the live-run
    protection of the two tests around this one exactly as it was.
    """

    executor = _ScriptedExecutor()
    runtime = _runtime(projection_store, store, executor)

    turn = commit_chat_turn(coordinator, "cm-settle", "I live in Berlin.", 1)
    runtime.run_after_turn(CONV, turn.turn_id)
    assert runtime._claimed_here == set()

    # A rejected run settles too (the deterministic-refusal edge).
    executor.failure = DomainError(
        code=DomainErrorCode.VALIDATION_FAILED, message="scope refused"
    )
    second = commit_chat_turn(coordinator, "cm-settle-2", "I read.", 2)
    runtime.run_after_turn(CONV, second.turn_id)
    assert runtime._claimed_here == set()

    # The raising case does NOT settle: that job is still this process's
    # live RUNNING row (the property the F-5 scan relies on).
    executor.failure = None
    executor.explode = True
    third = commit_chat_turn(coordinator, "cm-settle-3", "I keep a garden.", 3)
    assert isinstance(runtime.run_after_turn(CONV, third.turn_id), Err)
    assert len(runtime._claimed_here) == 1


def test_a_restarted_runtime_still_collects_the_previous_residue(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    projection_store: SqliteProjectionStore,
    coordinator: ConversationCoordinator,
) -> None:
    """F-5's other half: the claimed set is process-local, so a fresh
    instance (a restart) starts empty and does collect the dead process's
    RUNNING residue — and can run it to COMMITTED afterwards."""

    crashing = _ScriptedExecutor()
    crashing.explode = True
    first = _runtime(projection_store, store, crashing)
    turn = commit_chat_turn(coordinator, "cm-restart", "I live in Berlin.", 1)
    assert isinstance(first.run_after_turn(CONV, turn.turn_id), Err)
    job_id = projection_id_for(PROJECTION_TYPE_RELATIONSHIP, turn.turn_id)
    assert projection_job_row(db, job_id)[5] == "RUNNING"

    restarted = _runtime(projection_store, store, _ScriptedExecutor())
    reopened = restarted.recover_stale_running()
    assert isinstance(reopened, Ok)
    assert reopened.value == (job_id,)
    assert projection_job_row(db, job_id)[5] == "FAILED_RETRYABLE"

    runs = restarted.run_after_turn(CONV, turn.turn_id)
    # P4-3 semantic sync: only the RELATIONSHIP job has a scripted executor
    # in this assembly, so the run reports it COMMITTED and the EPISODE job
    # (no executor registered here) REJECTED as unsupported — the pin below
    # is the RELATIONSHIP half it has always been about.
    assert [item.status.value for item in _runs_of(runs)] == ["COMMITTED"]
    assert projection_job_row(db, job_id)[6] == 2


# -- ④ the crash gap --------------------------------------------------------


def test_a_crash_gap_is_repaired_from_the_deterministic_id(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    projection_runtime: CP4ProjectionRuntime,
    coordinator: ConversationCoordinator,
) -> None:
    """The turn completed and its job row is not there (the crash
    simulation): ``ensure_projection_jobs`` recreates exactly that row,
    idempotently, and the job then runs to COMMITTED.

    The conversation carries a persona, so the real executors can compute
    their bases and actually commit.

    P4-3 semantic sync: the repair is per ``(projection_type, turn)`` pair
    now, so one call restores both types' rows (this pin keeps reading the
    RELATIONSHIP row it has always been about, and the row counts move with
    the supported-type count).
    """

    conversation = open_conversation_for(store, "conv-gap-persona", PERSONA_A)
    turn = commit_chat_turn(
        coordinator, "cm-gap", "I live in Berlin.", 1, conversation=conversation
    )
    assert projection_job_rows(db) == []
    job_id = projection_id_for(PROJECTION_TYPE_RELATIONSHIP, turn.turn_id)
    absent = projection_runtime.job_view(job_id)
    assert isinstance(absent, Ok) and absent.value is None

    ensured = projection_runtime.ensure_projection_jobs(turn.turn_id)
    assert isinstance(ensured, Ok)
    assert ensured.value[0] == job_id
    assert len(ensured.value) == len(SUPPORTED_PROJECTION_TYPES)
    assert len(projection_job_rows(db)) == len(SUPPORTED_PROJECTION_TYPES)
    assert projection_job_row(db, job_id)[5] == "PENDING"
    # The repaired row is the *current* slice's job: its recorded hash is
    # the live slice's digest, so the next run will not reject it.
    assert projection_job_row(db, job_id)[3] == turn_slice_hash(
        turn_slice(store, turn.turn_id)
    )

    # Repeating the repair is a replay: the same rows, untouched.
    again = projection_runtime.ensure_projection_jobs(turn.turn_id)
    assert isinstance(again, Ok) and again.value[0] == job_id
    assert len(projection_job_rows(db)) == len(SUPPORTED_PROJECTION_TYPES)
    assert projection_job_row(db, job_id)[6] == 0

    runs = projection_runtime.run_after_turn(conversation, turn.turn_id)
    assert [item.status.value for item in _runs_of(runs)] == ["COMMITTED"]
    assert projection_job_row(db, job_id)[5] == "COMMITTED"
    assert projection_job_row(db, job_id)[6] == 1


def test_the_missing_job_scan_finds_exactly_the_gap(
    db: sqlite3.Connection,
    projection_runtime: CP4ProjectionRuntime,
    coordinator: ConversationCoordinator,
) -> None:
    first = commit_chat_turn(coordinator, "cm-scan-1", "I live in Berlin.", 1)
    second = commit_chat_turn(coordinator, "cm-scan-2", "I read every evening.", 2)
    # Turn 1 gets its jobs; turn 2 stays a crash gap.
    assert isinstance(
        projection_runtime.ensure_projection_jobs(first.turn_id), Ok
    )

    missing = projection_runtime.ensure_missing_jobs()
    assert isinstance(missing, Ok)
    # P4-3 semantic sync: the scan walks one supported type at a time and the
    # per-turn repair returns that turn's ids in SUPPORTED_PROJECTION_TYPES
    # order, so a turn missing both types reports both — RELATIONSHIP first,
    # EPISODE second. Same gap, same deterministic ids, two rows.
    assert missing.value == (
        projection_id_for(PROJECTION_TYPE_RELATIONSHIP, second.turn_id),
        projection_id_for(PROJECTION_TYPE_EPISODE, second.turn_id),
    )
    # The scan is idempotent: the second pass has nothing left to repair.
    empty = projection_runtime.ensure_missing_jobs()
    assert isinstance(empty, Ok) and empty.value == ()
    assert len(projection_job_rows(db)) == 2 * len(SUPPORTED_PROJECTION_TYPES)


def test_a_conflicting_payload_on_the_deterministic_id_is_a_conflict(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    projection_store: SqliteProjectionStore,
    projection_runtime: CP4ProjectionRuntime,
    coordinator: ConversationCoordinator,
) -> None:
    """The deterministic id names one job: a row for the same turn whose
    payload differs is a CONFLICT, never a silent overwrite — and the queue
    still gets its run, so the clashing row is resolved deterministically
    instead of blocking the conversation."""

    executor = _ScriptedExecutor()
    runtime = _runtime(projection_store, store, executor)
    turn = commit_chat_turn(coordinator, "cm-conflict", "I live in Berlin.", 1)
    job_id = projection_id_for(PROJECTION_TYPE_RELATIONSHIP, turn.turn_id)
    assert isinstance(
        projection_store.enqueue_projection(
            _job(
                job_id=job_id,
                turn_id=turn.turn_id,
                source_version="a-different-hash",
            )
        ),
        Ok,
    )
    refused = projection_runtime.ensure_projection_jobs(turn.turn_id)
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.CONFLICT

    # run_after_turn reports the enqueue refusal *and* still runs the queue:
    # the clashing row cannot be computed from the current slice, so it is
    # rejected, and the conversation is left with no unfinished work.
    ran = runtime.run_after_turn(CONV, turn.turn_id)
    assert isinstance(ran, Err)
    assert ran.error.code is DomainErrorCode.CONFLICT
    assert projection_job_row(db, job_id)[5] == "REJECTED"
    assert projection_job_row(db, job_id)[6] == 0
