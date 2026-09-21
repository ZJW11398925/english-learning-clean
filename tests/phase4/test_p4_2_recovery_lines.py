"""P4-2 ⑦ — the recovery lines of the startup pass (TASK-OPI-4d516e4f.9 B5).

``ConversationCoordinator.run_startup_recovery`` gains three lines beside the
P3-3 scan/sweep/reconcile (DEC-…5ba74efc.96 F1/F2 and the CP4 sweep):

- the durable PENDING teaching-evidence backlog is landed (F2, RA §21 "durable
  proposal pending");
- every §17 ``evidence_proposal_refs`` entry is checked against Learning's
  own proposal read, and the dangling ones are reported (F1);
- the CP4 stale RUNNING residue is re-opened, the crash gaps are repaired
  from their deterministic ids, and the conversations holding either kind of
  work get one run.

All three are optional ports and all three are failure-tolerant: an ``Err``
or a raised exception marks the line unavailable and startup still completes
(a durable backlog is work for the *next* pass, never a reason for this
process to fail to start). Every existing construction/equality assertion
over the pre-P4-2 three fields keeps its exact meaning — pinned here too.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from elc.learning.controller import LearningController
from elc.learning.store import (
    SqliteLearningStore,
    teaching_evidence_proposal_id,
)
from elc.platform.db.projection_store import SqliteProjectionStore
from elc.platform.types import (
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
)
from elc.runtime.controller import (
    ConversationCoordinator,
    StartupRecoveryOutcome,
)
from elc.runtime.projections import (
    PROJECTION_TYPE_EPISODE,
    PROJECTION_TYPE_RELATIONSHIP,
    CP4ProjectionRuntime,
    projection_id_for,
)
from elc.runtime.types import ProjectionJobRecord, ProjectionJobState

from .conftest import (
    CANONICAL_ANSWER,
    PERSONA_A,
    commit_chat_turn,
    open_conversation_for,
    open_moment,
    projection_job_row,
    projection_job_rows,
    reply_ok,
)
from .conftest import attempt as make_attempt


def _runs_of(
    runs, projection_type: str = PROJECTION_TYPE_RELATIONSHIP
) -> list:
    """The run results of one projection type (P4-3 semantic sync).

    The startup drain runs every unfinished job of the conversations it
    visited, and there is now one job per supported type; these pins are
    about the RELATIONSHIP job they have always named, so they select by
    type instead of by position (``pending_projections`` orders by
    ``created_at, projection_id``, which fixes no order between types).
    """

    return [item for item in runs if item.projection_type == projection_type]


def _proposal_status(db: sqlite3.Connection, proposal_id: str) -> str:
    row = db.execute(
        "SELECT status FROM teaching_evidence_proposal WHERE proposal_id = ?",
        (proposal_id,),
    ).fetchone()
    assert row is not None, f"proposal not durable: {proposal_id}"
    return str(row[0])


def _evaluation_refs(db: sqlite3.Connection, evaluation_id: str) -> list[str]:
    row = db.execute(
        "SELECT evidence_proposal_refs FROM attempt_evaluation_record"
        " WHERE attempt_evaluation_id = ?",
        (evaluation_id,),
    ).fetchone()
    assert row is not None, f"evaluation not durable: {evaluation_id}"
    return list(json.loads(str(row[0])))


# -- F2: the durable pending evidence backlog -------------------------------


def test_startup_lands_the_pending_teaching_evidence_backlog(
    db: sqlite3.Connection,
    coordinator: ConversationCoordinator,
    monkeypatch,
) -> None:
    """A proposal left PENDING by a failed commit is exactly the residue a
    new epoch may land: startup retries it, Learning decides again, and the
    row flips COMMITTED."""

    original = SqliteLearningStore.commit_evidence_group
    state = {"fail": True}

    def flaky(self: SqliteLearningStore, group: Any, **kwargs: Any):
        if state["fail"]:
            return Err(
                DomainError(
                    code=DomainErrorCode.CONFLICT,
                    message="learning commit unavailable (injected)",
                )
            )
        return original(self, group, **kwargs)

    monkeypatch.setattr(SqliteLearningStore, "commit_evidence_group", flaky)

    open_moment(coordinator, "cm-f2-open")
    reply = reply_ok(coordinator, make_attempt(CANONICAL_ANSWER), "cm-f2-reply")
    proposal_id = teaching_evidence_proposal_id(str(reply.attempt_id))
    assert reply.evidence_commit_id is None
    assert _proposal_status(db, proposal_id) == "PENDING"

    state["fail"] = False
    outcome = coordinator.run_startup_recovery()
    assert isinstance(outcome, Ok), outcome
    assert outcome.value.committed_evidence_proposals == (proposal_id,)
    assert outcome.value.teaching_evidence_retry_unavailable is False
    assert _proposal_status(db, proposal_id) == "COMMITTED"
    # The plan half of the same pass is unchanged (nothing old-epoch here).
    assert outcome.value.plan == ()


def test_a_raising_retry_marks_the_line_unavailable_and_startup_completes(
    coordinator: ConversationCoordinator,
    monkeypatch,
) -> None:
    def exploding(self: LearningController) -> None:
        raise RuntimeError("learning store exploded (injected)")

    monkeypatch.setattr(
        LearningController, "retry_pending_teaching_evidence", exploding
    )
    outcome = coordinator.run_startup_recovery()
    assert isinstance(outcome, Ok), outcome
    assert outcome.value.teaching_evidence_retry_unavailable is True
    assert outcome.value.committed_evidence_proposals == ()
    # The other lines still ran — one optional port cannot stop the pass.
    assert outcome.value.plan == ()
    assert outcome.value.evidence_ref_scan_unavailable is False


# -- F1: the refs↔proposal reconciliation -----------------------------------


def test_a_dangling_evidence_ref_is_reported(
    db: sqlite3.Connection,
    coordinator: ConversationCoordinator,
    monkeypatch,
) -> None:
    """The genuine dangling case: the evidence leg degrades before the
    proposal is written, so the evaluation's §17 ref points at a row that
    does not exist. The scan names it instead of hiding it."""

    original = SqliteLearningStore.record_opportunity

    def dropping(self: SqliteLearningStore, **kwargs: Any):
        del self, kwargs
        return Err(
            DomainError(
                code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                message="learning unavailable (injected)",
            )
        )

    monkeypatch.setattr(SqliteLearningStore, "record_opportunity", dropping)
    open_moment(coordinator, "cm-f1-open")
    reply = reply_ok(coordinator, make_attempt(CANONICAL_ANSWER), "cm-f1-reply")
    monkeypatch.setattr(SqliteLearningStore, "record_opportunity", original)

    attempt_id = str(reply.attempt_id)
    evaluation_id = f"ae-{attempt_id}"
    ref = f"tep-{attempt_id}"
    assert reply.evidence_commit_id is None
    assert db.execute(
        "SELECT COUNT(*) FROM teaching_evidence_proposal"
    ).fetchone() == (0,)
    assert _evaluation_refs(db, evaluation_id) == [ref]

    outcome = coordinator.run_startup_recovery()
    assert isinstance(outcome, Ok), outcome
    assert outcome.value.evidence_ref_scan_unavailable is False
    assert [
        (item.evaluation_id, item.ref)
        for item in outcome.value.dangling_evidence_refs
    ] == [(evaluation_id, ref)]


def test_the_teaching_controller_is_the_ref_scan_source(
    teaching_controller,
) -> None:
    """The F1 seam: the Teaching authority face *is* the runtime's
    ``TeachingEvidenceRefSource``, so the startup line can ask it for the
    refs without the runtime touching SQL and without the teaching package
    importing Learning."""

    from elc.runtime.recovery import TeachingEvidenceRefSource

    assert isinstance(teaching_controller, TeachingEvidenceRefSource)


def test_a_resolved_ref_is_not_reported(
    db: sqlite3.Connection,
    coordinator: ConversationCoordinator,
) -> None:
    """The positive control: the same world, one happy reply — the ref
    resolves to its durable proposal row and nothing is reported."""

    open_moment(coordinator, "cm-f1-ok-open")
    reply = reply_ok(coordinator, make_attempt(CANONICAL_ANSWER), "cm-f1-ok")
    attempt_id = str(reply.attempt_id)
    assert _evaluation_refs(db, f"ae-{attempt_id}") == [f"tep-{attempt_id}"]
    assert db.execute(
        "SELECT COUNT(*) FROM teaching_evidence_proposal WHERE proposal_id = ?",
        (f"tep-{attempt_id}",),
    ).fetchone() == (1,)

    outcome = coordinator.run_startup_recovery()
    assert isinstance(outcome, Ok), outcome
    assert outcome.value.dangling_evidence_refs == ()
    assert outcome.value.evidence_ref_scan_unavailable is False


def test_every_ref_is_checked_whatever_its_shape(
    db: sqlite3.Connection,
    coordinator: ConversationCoordinator,
) -> None:
    """The check is a durable existence read over *every* ref — no prefix
    filter, no re-derived id: a ref of a shape nobody recognizes is still a
    ref that has to resolve."""

    open_moment(coordinator, "cm-f1-shape-open")
    reply = reply_ok(coordinator, make_attempt(CANONICAL_ANSWER), "cm-f1-shape")
    attempt_id = str(reply.attempt_id)
    evaluation_id = f"ae-{attempt_id}"
    foreign = "ref-of-an-unknown-shape"
    db.execute(
        "UPDATE attempt_evaluation_record SET evidence_proposal_refs = ?"
        " WHERE attempt_evaluation_id = ?",
        (json.dumps([f"tep-{attempt_id}", foreign]), evaluation_id),
    )
    db.commit()  # close the implicit tx before the store's own unit

    outcome = coordinator.run_startup_recovery()
    assert isinstance(outcome, Ok), outcome
    assert [
        (item.evaluation_id, item.ref)
        for item in outcome.value.dangling_evidence_refs
    ] == [(evaluation_id, foreign)]


# -- the CP4 startup sweep --------------------------------------------------


def test_the_startup_sweep_repairs_a_crash_gap_and_runs_it(
    db: sqlite3.Connection,
    store,
    projecting_coordinator: ConversationCoordinator,
) -> None:
    """A job lost between the turn's commit points comes back under the
    deterministic id and runs to COMMITTED in the same startup pass."""

    conversation = open_conversation_for(store, "conv-startup-gap", PERSONA_A)
    turn = commit_chat_turn(
        projecting_coordinator,
        "cm-startup-gap",
        "I live in Berlin.",
        1,
        conversation=conversation,
    )
    job_id = projection_id_for(PROJECTION_TYPE_RELATIONSHIP, turn.turn_id)
    episode_job_id = projection_id_for(PROJECTION_TYPE_EPISODE, turn.turn_id)
    assert projection_job_row(db, job_id)[5] == "COMMITTED"

    # The crash simulation: neither of the turn's rows was ever written
    # (P4-3: a turn owns one job per supported type, and the gap is per row).
    db.execute(
        "DELETE FROM projection_job WHERE source_turn_id = ?",
        (str(turn.turn_id),),
    )
    db.commit()  # close the implicit tx before the store's own unit
    assert projection_job_rows(db) == []

    outcome = projecting_coordinator.run_startup_recovery()
    assert isinstance(outcome, Ok), outcome
    # Both gaps are repaired from their own deterministic ids, in
    # SUPPORTED_PROJECTION_TYPES order.
    assert outcome.value.projection_jobs == (job_id, episode_job_id)
    assert outcome.value.projection_recovery_unavailable is False
    assert [item.status.value for item in _runs_of(
        outcome.value.projection_runs
    )] == ["COMMITTED"]
    assert _runs_of(outcome.value.projection_runs)[0].projection_job_id == job_id
    assert projection_job_row(db, job_id)[5] == "COMMITTED"
    # Idempotent: the next pass has nothing left to repair.
    again = projecting_coordinator.run_startup_recovery()
    assert isinstance(again, Ok)
    assert again.value.projection_jobs == ()
    assert again.value.projection_runs == ()


def test_a_broken_projection_line_marks_itself_unavailable(
    db: sqlite3.Connection,
    projecting_coordinator: ConversationCoordinator,
    monkeypatch,
) -> None:
    """Startup must still complete when the projection line cannot run —
    both failure shapes are trapped and named."""

    def exploding(self: CP4ProjectionRuntime) -> None:
        raise RuntimeError("projection store exploded (injected)")

    monkeypatch.setattr(CP4ProjectionRuntime, "ensure_missing_jobs", exploding)
    outcome = projecting_coordinator.run_startup_recovery()
    assert isinstance(outcome, Ok), outcome
    assert outcome.value.projection_recovery_unavailable is True
    assert outcome.value.projection_jobs == ()
    assert outcome.value.projection_runs == ()
    assert outcome.value.plan == ()

    monkeypatch.undo()

    def refusing(self: SqliteProjectionStore, projection_type: str):
        del self, projection_type
        return Err(
            DomainError(
                code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                message="projection store unavailable (injected)",
            )
        )

    monkeypatch.setattr(
        SqliteProjectionStore, "turns_missing_projection", refusing
    )
    second = projecting_coordinator.run_startup_recovery()
    assert isinstance(second, Ok), second
    assert second.value.projection_recovery_unavailable is True
    assert second.value.projection_jobs == ()
    del db


# -- the stale RUNNING residue (the claim that never reported) -------------


def test_a_stale_running_job_is_reopened_and_committed(
    db: sqlite3.Connection,
    store,
    projection_store: SqliteProjectionStore,
    projection_runtime: CP4ProjectionRuntime,
    coordinator: ConversationCoordinator,
    projecting_coordinator: ConversationCoordinator,
) -> None:
    """The crash window between claim and completion: the row says RUNNING
    and no process will ever finish it. The startup pass re-opens it and the
    ordinary retry path lands it — attempt_count shows the second attempt."""

    conversation = open_conversation_for(store, "conv-stale", PERSONA_A)
    turn = commit_chat_turn(
        coordinator, "cm-stale", "I live in Berlin.", 1, conversation=conversation
    )
    ensured = projection_runtime.ensure_projection_jobs(turn.turn_id)
    assert isinstance(ensured, Ok)
    # P4-3 semantic sync: the ensure face returns one id per supported type,
    # RELATIONSHIP first — the job this pin has always claimed.
    job_id = ensured.value[0]
    claimed = projection_store.claim_projection(job_id, base_version="rv-crashed")
    assert isinstance(claimed, Ok)
    assert claimed.value.status is ProjectionJobState.RUNNING
    assert claimed.value.attempt_count == 1

    outcome = projecting_coordinator.run_startup_recovery()
    assert isinstance(outcome, Ok), outcome
    assert outcome.value.projection_recovery_unavailable is False
    assert outcome.value.reopened_projections == (job_id,)
    assert [item.status.value for item in _runs_of(
        outcome.value.projection_runs
    )] == ["COMMITTED"]
    row = projection_job_row(db, job_id)
    assert row[5] == "COMMITTED"
    assert row[6] == 2  # the re-opened row was claimed a second time
    # The executor ran: the crashed claim's base was replaced by a freshly
    # recomputed one (only the executor's base_version produces it).
    assert row[4] != "rv-crashed"
    assert row[4] is not None


def test_the_reopen_scan_is_idempotent(
    db: sqlite3.Connection,
    store,
    projection_store: SqliteProjectionStore,
    projection_runtime: CP4ProjectionRuntime,
    coordinator: ConversationCoordinator,
    projecting_coordinator: ConversationCoordinator,
) -> None:
    """A second startup pass has no RUNNING residue left: nothing is
    re-opened, nothing is repaired, nothing re-runs — and the landed row is
    byte-for-byte where the first pass left it."""

    conversation = open_conversation_for(store, "conv-stale-twice", PERSONA_A)
    turn = commit_chat_turn(
        coordinator, "cm-stale-twice", "I live in Berlin.", 1,
        conversation=conversation,
    )
    asserted = projection_runtime.ensure_projection_jobs(turn.turn_id)
    assert isinstance(asserted, Ok)
    job_id = asserted.value[0]  # RELATIONSHIP, the supported-type order
    assert isinstance(
        projection_store.claim_projection(job_id, base_version="rv-crashed"), Ok
    )

    first = projecting_coordinator.run_startup_recovery()
    assert isinstance(first, Ok)
    assert first.value.reopened_projections == (job_id,)
    settled = projection_job_row(db, job_id)

    again = projecting_coordinator.run_startup_recovery()
    assert isinstance(again, Ok), again
    assert again.value.reopened_projections == ()
    assert again.value.projection_jobs == ()
    assert again.value.projection_runs == ()
    assert projection_job_row(db, job_id) == settled
    assert projection_job_row(db, job_id)[6] == 2


def test_the_reopen_scan_touches_nothing_but_running_rows(
    db: sqlite3.Connection,
    store,
    projection_store: SqliteProjectionStore,
    projection_runtime: CP4ProjectionRuntime,
    coordinator: ConversationCoordinator,
) -> None:
    """Only RUNNING is stale residue: a PENDING row is claimable work and a
    COMMITTED row is finished work, so the scan leaves both exactly as they
    were (same bytes, attempt counters included)."""

    conversation = open_conversation_for(store, "conv-stale-only", PERSONA_A)
    pending_turn = commit_chat_turn(
        coordinator, "cm-only-p", "I live in Berlin.", 1,
        conversation=conversation,
    )
    running_turn = commit_chat_turn(
        coordinator, "cm-only-r", "I read every evening.", 2,
        conversation=conversation,
    )
    committed_turn = commit_chat_turn(
        coordinator, "cm-only-c", "I keep a garden.", 3,
        conversation=conversation,
    )
    jobs = {}
    for name, turn in (
        ("pending", pending_turn),
        ("running", running_turn),
        ("committed", committed_turn),
    ):
        ensured = projection_runtime.ensure_projection_jobs(turn.turn_id)
        assert isinstance(ensured, Ok)
        # The RELATIONSHIP job of each turn (SUPPORTED_PROJECTION_TYPES
        # order); the EPISODE jobs of the same turns are left PENDING, which
        # is exactly the "claimable work is not residue" case this pin is
        # about, one type over.
        jobs[name] = ensured.value[0]
    assert isinstance(
        projection_store.claim_projection(
            jobs["running"], base_version="rv-crashed"
        ),
        Ok,
    )
    assert isinstance(
        projection_store.claim_projection(
            jobs["committed"], base_version="rv-1"
        ),
        Ok,
    )
    assert isinstance(projection_store.complete_projection(jobs["committed"]), Ok)
    untouched = {
        name: projection_job_row(db, job_id)
        for name, job_id in jobs.items()
        if name != "running"
    }

    reopened = projection_runtime.recover_stale_running()
    assert isinstance(reopened, Ok), reopened
    assert reopened.value == (jobs["running"],)
    re_opened = projection_job_row(db, jobs["running"])
    assert re_opened[5] == "FAILED_RETRYABLE"
    assert re_opened[6] == 1  # re-opening is not an attempt
    for name, row in untouched.items():
        assert projection_job_row(db, jobs[name]) == row, name


def test_a_reopened_job_still_passes_the_slice_hash_revalidation(
    db: sqlite3.Connection,
    store,
    projection_store: SqliteProjectionStore,
    coordinator: ConversationCoordinator,
    projecting_coordinator: ConversationCoordinator,
) -> None:
    """Re-opening is not a replay: the row goes back on the ordinary retry
    edge, so the next run still revalidates ``source_turn_slice_hash`` —
    a moved slice is rejected, never blindly re-projected."""

    conversation = open_conversation_for(store, "conv-stale-hash", PERSONA_A)
    turn = commit_chat_turn(
        coordinator, "cm-stale-hash", "I live in Berlin.", 1,
        conversation=conversation,
    )
    job_id = projection_id_for(PROJECTION_TYPE_RELATIONSHIP, turn.turn_id)
    stale = projection_store.enqueue_projection(
        ProjectionJobRecord(
            projection_job_id=job_id,
            conversation_id=str(conversation),
            source_turn_id=turn.turn_id,
            projection_type=PROJECTION_TYPE_RELATIONSHIP,
            source_version="a-hash-the-slice-no-longer-has",
            state=ProjectionJobState.PENDING,
        )
    )
    assert isinstance(stale, Ok)
    assert isinstance(
        projection_store.claim_projection(job_id, base_version="rv-crashed"), Ok
    )

    outcome = projecting_coordinator.run_startup_recovery()
    assert isinstance(outcome, Ok), outcome
    assert outcome.value.reopened_projections == (job_id,)
    assert [item.status.value for item in _runs_of(
        outcome.value.projection_runs
    )] == ["REJECTED"]
    assert _runs_of(outcome.value.projection_runs)[0].detail == (
        "source_turn_slice_hash changed"
    )
    row = projection_job_row(db, job_id)
    assert row[5] == "REJECTED"
    assert row[6] == 1  # no second claim
    assert row[4] == "rv-crashed"  # no base was recomputed


# -- F-2: the startup pass drains the whole registered backlog -------------


def test_startup_drains_a_registry_only_pending_row(
    db: sqlite3.Connection,
    store,
    projection_runtime: CP4ProjectionRuntime,
    coordinator: ConversationCoordinator,
    projecting_coordinator: ConversationCoordinator,
) -> None:
    """The reviewer's probe O: a PENDING row that is neither a crash gap (the
    row exists) nor RUNNING (nothing crashed mid-run) — enqueued, then the
    process died before its run. The registry is the ground truth of work
    that still has to happen, so startup drains it."""

    conversation = open_conversation_for(store, "conv-registry", PERSONA_A)
    turn = commit_chat_turn(
        coordinator, "cm-registry", "I live in Berlin.", 1,
        conversation=conversation,
    )
    ensured = projection_runtime.ensure_projection_jobs(turn.turn_id)
    assert isinstance(ensured, Ok)
    # P4-3 semantic sync: one id per supported type (RELATIONSHIP first);
    # both rows are PENDING and the drain below finishes both.
    job_id = ensured.value[0]
    assert projection_job_row(db, job_id)[5] == "PENDING"
    assert projection_job_row(db, job_id)[6] == 0

    outcome = projecting_coordinator.run_startup_recovery()
    assert isinstance(outcome, Ok), outcome
    assert outcome.value.projection_recovery_unavailable is False
    assert outcome.value.projection_jobs == ()  # nothing was missing
    assert outcome.value.reopened_projections == ()  # nothing was RUNNING
    assert [item.status.value for item in _runs_of(
        outcome.value.projection_runs
    )] == ["COMMITTED"]
    assert _runs_of(outcome.value.projection_runs)[0].projection_job_id == job_id
    assert projection_job_row(db, job_id)[5] == "COMMITTED"
    assert projection_job_row(db, job_id)[6] == 1


def test_startup_drains_a_registry_only_failed_retryable_row(
    db: sqlite3.Connection,
    store,
    projection_store: SqliteProjectionStore,
    projection_runtime: CP4ProjectionRuntime,
    coordinator: ConversationCoordinator,
    projecting_coordinator: ConversationCoordinator,
) -> None:
    """The same rule for a transiently failed row nobody came back for: it
    is in the registry, so the startup pass finishes it."""

    conversation = open_conversation_for(store, "conv-registry-retry", PERSONA_A)
    turn = commit_chat_turn(
        coordinator, "cm-registry-retry", "I live in Berlin.", 1,
        conversation=conversation,
    )
    ensured = projection_runtime.ensure_projection_jobs(turn.turn_id)
    assert isinstance(ensured, Ok)
    job_id = ensured.value[0]  # RELATIONSHIP, the supported-type order
    assert isinstance(
        projection_store.claim_projection(job_id, base_version="rv-1"), Ok
    )
    assert isinstance(projection_store.fail_projection(job_id), Ok)
    assert projection_job_row(db, job_id)[5] == "FAILED_RETRYABLE"

    outcome = projecting_coordinator.run_startup_recovery()
    assert isinstance(outcome, Ok), outcome
    assert [item.status.value for item in _runs_of(
        outcome.value.projection_runs
    )] == ["COMMITTED"]
    assert projection_job_row(db, job_id)[5] == "COMMITTED"
    assert projection_job_row(db, job_id)[6] == 2


def test_the_post_turn_path_stays_conversation_scoped(
    db: sqlite3.Connection,
    store,
    projection_store: SqliteProjectionStore,
    projection_runtime: CP4ProjectionRuntime,
    coordinator: ConversationCoordinator,
    projecting_coordinator: ConversationCoordinator,
) -> None:
    """F-2's other half: only *startup* drains the registry. A post-turn run
    for conversation B must leave conversation A's registered-but-unrun work
    exactly where it is — the live path stays conversation-scoped."""

    conv_a = open_conversation_for(store, "conv-scope-a", PERSONA_A)
    conv_b = open_conversation_for(store, "conv-scope-b", PERSONA_A)
    turn_a = commit_chat_turn(
        coordinator, "cm-scope-a", "I live in Berlin.", 1, conversation=conv_a
    )
    ensured = projection_runtime.ensure_projection_jobs(turn_a.turn_id)
    assert isinstance(ensured, Ok)
    # The RELATIONSHIP job of A; its EPISODE job is PENDING too and stays
    # that way, which is the same "registered work is not run by B's turn"
    # fact one type over.
    job_a = ensured.value[0]
    assert projection_job_row(db, job_a)[5] == "PENDING"
    del projection_store

    turn_b = commit_chat_turn(
        projecting_coordinator,
        "cm-scope-b",
        "I read every evening.",
        2,
        conversation=conv_b,
    )
    job_b = projection_id_for(PROJECTION_TYPE_RELATIONSHIP, turn_b.turn_id)
    assert projection_job_row(db, job_b)[5] == "COMMITTED"
    # Conversation A's registered work is untouched by B's post-turn run.
    assert projection_job_row(db, job_a)[5] == "PENDING"
    assert projection_job_row(db, job_a)[6] == 0


# -- the pre-P4-2 shape stays exact -----------------------------------------

def test_an_assembly_without_the_p4_2_ports_keeps_the_old_outcome_shape(
    db: sqlite3.Connection,
    coordinator: ConversationCoordinator,
) -> None:
    """B5's compatibility rule: the new fields are defaulted, so the outcome
    still equals the three-field construction — and an assembly without the
    projection port reports "not read", never a fabricated fact."""

    del db
    outcome = coordinator.run_startup_recovery()
    assert isinstance(outcome, Ok), outcome
    assert outcome.value == StartupRecoveryOutcome(
        plan=(), recovered_moments=(), closed_turns=()
    )
    assert outcome.value.projection_jobs == ()
    assert outcome.value.projection_runs == ()
    assert outcome.value.projection_recovery_unavailable is False
    assert outcome.value.committed_evidence_proposals == ()
    assert outcome.value.teaching_evidence_retry_unavailable is False
    assert outcome.value.dangling_evidence_refs == ()
    assert outcome.value.evidence_ref_scan_unavailable is False
