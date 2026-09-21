"""P4-0 ① — the durable pending teaching-evidence proposal (RA §21).

The semantic gap this closes (DEC-…5ba74efc.68 C1): before P4-0 an attempt's
AttemptRecord and AttemptEvaluationRecord were durable while the evidence
they produced could be lost with the process — the evaluation's
``evidence_proposal_refs`` named a group that might never exist. The chain is
now Attempt → Evaluation → **proposal PENDING durable (own short
transaction)** → commit attempt, and all three outcomes are durable facts:

- COMMITTED — the evidence landed in the kernel;
- REJECTED — Learning's validation refused it (a deterministic verdict);
- PENDING — the commit could not run; the teaching turn keeps its normal
  persona and the proposal waits for the explicit retry face.

What is asserted here: the durable-pending counterexample end to end
(inject a commit failure → PENDING survives → retry → LearnerState moves →
no duplicate evidence), the idempotent replay of a committed proposal, the
crash-between-commit-and-verdict case, the REJECTED branch, the
double-namespace reconciliation between the teaching-side refs
(``tep-``) and the committed group (``eg-teaching-``), and the ownership
red line: the proposal is Learning's own table and never a ``projection_job``
row.

Test-side seams (declared): the commit failure is injected by wrapping
``SqliteLearningStore.commit_evidence_group`` (the last step of the chain)
with a flaky delegate, and the crash-between-commit-and-verdict case by
dropping the store's internal ``_settle_proposal`` call once. Both wrap the
real implementation; neither replaces it with a fake.
"""

from __future__ import annotations

import ast
import hashlib
import json
import sqlite3
from collections.abc import Iterator
from typing import Any

import pytest

from elc.learning.controller import LearningController
from elc.learning.store import (
    TEACHING_EVIDENCE_GROUP_PREFIX,
    TEACHING_EVIDENCE_PROPOSAL_PREFIX,
    SqliteLearningStore,
    teaching_evidence_group_id,
    teaching_evidence_proposal_id,
)
from elc.platform.types import (
    DomainError,
    DomainErrorCode,
    Err,
    LearningOpportunityId,
    Ok,
    TargetId,
)
from elc.runtime.controller import ConversationCoordinator
from elc.teaching.evaluator import AttemptEvaluation
from elc.teaching.flow import TEACHING_EVIDENCE_PROPOSAL_PREFIX as TEACHING_SIDE_PREFIX
from elc.teaching.flow import evidence_proposal_refs_for
from elc.teaching.types import AttemptOutcome
from tests.conftest import SRC_ROOT

from .conftest import (
    CANONICAL_ANSWER,
    FOCUS_TARGET,
    commit_chat_turn,
    open_moment,
    reply_ok,
)
from .conftest import attempt as make_attempt

MODALITY = "TEXT_PRODUCTION"


def _proposal_row(db: sqlite3.Connection, proposal_id: str) -> tuple[Any, ...]:
    row = db.execute(
        "SELECT proposal_id, source_attempt_id, source_evaluation_id,"
        " moment_id, provenance, payload, status, attempt_count,"
        " created_at, updated_at, committed_at"
        " FROM teaching_evidence_proposal WHERE proposal_id = ?",
        (proposal_id,),
    ).fetchone()
    assert row is not None, f"proposal {proposal_id} is not durable"
    return tuple(row)


def _single_attempt_id(db: sqlite3.Connection) -> str:
    row = db.execute(
        "SELECT attempt_id FROM attempt_record ORDER BY attempt_index"
    ).fetchone()
    assert row is not None
    return str(row[0])


def _counts(db: sqlite3.Connection) -> dict[str, int]:
    return {
        table: int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        for table in (
            "evidence_group",
            "evidence_claim",
            "evidence_commit",
            "projection_job",
        )
    }


@pytest.fixture()
def flaky_commit(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, bool]]:
    """Wrap the chain's last step so a commit failure can be injected and
    healed inside one test (the RA §21 "Learning commit unavailable" case)."""

    state = {"fail": True}
    original = SqliteLearningStore.commit_evidence_group

    def flaky(self: SqliteLearningStore, group, **kwargs: Any):
        if state["fail"]:
            return Err(
                DomainError(
                    code=DomainErrorCode.CONFLICT,
                    message="learning commit unavailable (injected)",
                )
            )
        return original(self, group, **kwargs)

    monkeypatch.setattr(SqliteLearningStore, "commit_evidence_group", flaky)
    yield state


def test_the_chain_records_a_durable_proposal_and_commits_it(
    db: sqlite3.Connection,
    coordinator: ConversationCoordinator,
    learning: SqliteLearningStore,
) -> None:
    opened = open_moment(coordinator, "cm-p4-happy-open")
    reply = reply_ok(coordinator, make_attempt(CANONICAL_ANSWER), "cm-p4-happy")

    attempt_id = str(reply.attempt_id)
    proposal_id = teaching_evidence_proposal_id(attempt_id)
    assert proposal_id == f"{TEACHING_EVIDENCE_PROPOSAL_PREFIX}{attempt_id}"

    row = _proposal_row(db, proposal_id)
    assert row[1] == attempt_id
    assert row[2] == f"ae-{attempt_id}"
    assert row[3] == str(opened.moment_id)
    assert row[6] == "COMMITTED"
    assert row[7] == 1
    assert row[10] is not None  # committed_at

    # Provenance: the target + the evaluator version + the payload hash.
    provenance = json.loads(str(row[4]))
    assert provenance["target_type"] == "RESOURCE"
    assert provenance["target_id"] == FOCUS_TARGET
    assert provenance["evaluator_id"] == "attempt-evaluator-v0"
    assert provenance["evaluator_version"] == "v0"
    assert provenance["payload_hash"] == hashlib.sha256(
        str(row[5]).encode("utf-8")
    ).hexdigest()

    # The payload is the claim document plus its commit context — enough to
    # replay the commit without any live teaching object.
    payload = json.loads(str(row[5]))
    assert payload["commit"]["evidence_group_id"] == (
        teaching_evidence_group_id(attempt_id)
    )
    assert payload["commit"]["source_turn_id"] == str(reply.turn_id)
    assert payload["claims"][0]["evidence_claim_id"].startswith("ecl-teaching-")
    assert payload["claims"][0]["opportunity_id"] == str(reply.opportunity_id)

    # §17 refs point at the proposal; the committed group is its isomorphic
    # sibling in the other namespace (P4-0 ① reconciliation).
    refs = db.execute(
        "SELECT evidence_proposal_refs FROM attempt_evaluation_record"
        " WHERE attempt_id = ?",
        (attempt_id,),
    ).fetchone()
    assert refs == (json.dumps([proposal_id]),)
    group = db.execute(
        "SELECT evidence_group_id FROM evidence_claim"
    ).fetchone()
    assert group == (teaching_evidence_group_id(attempt_id),)

    committed = learning.get_teaching_evidence_proposal(proposal_id)
    assert isinstance(committed, Ok) and committed.value is not None
    assert committed.value.status == "COMMITTED"
    assert committed.value.payload == str(row[5])
    assert reply.evidence_commit_id is not None
    assert _counts(db)["projection_job"] == 0


def test_a_failed_commit_leaves_the_proposal_pending_and_the_chat_alive(
    db: sqlite3.Connection,
    coordinator: ConversationCoordinator,
    learning: SqliteLearningStore,
    flaky_commit: dict[str, bool],
) -> None:
    """The reviewer's counterexample, end to end (DEC-…68 C1): the commit
    cannot run → the proposal is durable PENDING → the retry lands it →
    LearnerState moves → nothing is duplicated."""

    opened = open_moment(coordinator, "cm-p4-degrade-open")
    reply = reply_ok(coordinator, make_attempt(CANONICAL_ANSWER), "cm-p4-degrade")
    assert opened.gate_decision == "ALLOW"

    attempt_id = str(reply.attempt_id)
    proposal_id = teaching_evidence_proposal_id(attempt_id)
    # The Learning leg degraded: no commit id, no claims, watermark unmoved —
    # but the attempt, its evaluation and the pending proposal are durable.
    assert reply.evidence_commit_id is None
    assert reply.moment_state.value == "CLOSED"
    assert db.execute("SELECT COUNT(*) FROM active_teaching_lock").fetchone() == (
        0,
    )
    counts = _counts(db)
    assert counts["evidence_group"] == 0
    assert counts["evidence_claim"] == 0
    assert counts["evidence_commit"] == 0
    assert learning.get_evidence_watermark() == 0

    row = _proposal_row(db, proposal_id)
    assert row[6] == "PENDING"
    assert row[7] == 1  # the failed attempt is counted
    assert row[10] is None  # ... and nothing claims it committed
    assert db.execute(
        "SELECT outcome FROM attempt_evaluation_record WHERE attempt_id = ?",
        (attempt_id,),
    ).fetchone() == ("SUCCESS",)

    # The chat keeps its normal persona (RA §21) while the evidence waits.
    follow_up = commit_chat_turn(
        coordinator, "cm-p4-degrade-chat", "Anyway, how are you?", 2
    )
    assert follow_up.outcome == "REPLIED_FULL"
    assert follow_up.reply_text
    # (That ordinary turn commits its own evidence — so the baseline for the
    # retry assertions is taken now, and the teaching leg is read through its
    # own rows: the group/claim/commit of this attempt, and the watermark
    # delta.)
    group_id = teaching_evidence_group_id(attempt_id)
    watermark_before = learning.get_evidence_watermark()

    # The retry face: the backlog is committed from the durable payload.
    flaky_commit["fail"] = False
    retried = LearningController(learning).retry_pending_teaching_evidence()
    assert isinstance(retried, Ok), retried
    assert [proposal for proposal, _ in retried.value] == [proposal_id]
    commit_id = retried.value[0][1]

    row = _proposal_row(db, proposal_id)
    assert row[6] == "COMMITTED"
    assert row[7] == 2
    assert row[10] is not None
    assert db.execute(
        "SELECT COUNT(*) FROM evidence_group WHERE evidence_group_id = ?",
        (group_id,),
    ).fetchone() == (1,)
    assert db.execute(
        "SELECT COUNT(*) FROM evidence_claim WHERE evidence_group_id = ?",
        (group_id,),
    ).fetchone() == (1,)
    assert db.execute(
        "SELECT COUNT(*) FROM evidence_commit WHERE evidence_group_id = ?",
        (group_id,),
    ).fetchone() == (1,)
    assert learning.get_evidence_watermark() == watermark_before + 1
    committed_counts = _counts(db)

    # LearnerState really moves — the pending evidence was not just a row.
    rebuilt = learning.rebuild_learner_state(
        TargetId(FOCUS_TARGET), MODALITY
    )
    assert isinstance(rebuilt, Ok), rebuilt
    state = learning.get_learner_target_state(TargetId(FOCUS_TARGET), MODALITY)
    assert isinstance(state, Ok) and state.value is not None
    assert state.value.dimensions["independent_production"].estimate is not None

    # A second retry is a no-op: the backlog is empty and nothing doubles.
    again = LearningController(learning).retry_pending_teaching_evidence()
    assert isinstance(again, Ok) and again.value == ()
    assert _counts(db) == committed_counts
    assert learning.get_evidence_watermark() == watermark_before + 1
    # ... and the deterministic commit id of the first retry is the durable
    # one: a direct replay returns the same id without writing.
    replay = learning.commit_teaching_evidence_proposal(proposal_id)
    assert isinstance(replay, Ok) and replay.value == commit_id


def test_a_crash_between_the_commit_and_its_verdict_never_double_counts(
    db: sqlite3.Connection,
    coordinator: ConversationCoordinator,
    learning: SqliteLearningStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The harshest crash window: the evidence transaction committed and the
    process died before the verdict flip. The row stays PENDING while the
    claims are durable; the retry finds the durable commit and returns the
    *same* id — no second group, no second claim, no second watermark move."""

    original = SqliteLearningStore._settle_proposal  # noqa: SLF001
    state = {"dropped": False}

    def dropping(self: SqliteLearningStore, proposal_id: str, status: str):
        if state["dropped"]:
            return  # the process died before the verdict was written
        original(self, proposal_id, status)

    monkeypatch.setattr(SqliteLearningStore, "_settle_proposal", dropping)

    open_moment(coordinator, "cm-p4-crash-open")
    state["dropped"] = True
    reply = reply_ok(coordinator, make_attempt(CANONICAL_ANSWER), "cm-p4-crash")

    attempt_id = str(reply.attempt_id)
    proposal_id = teaching_evidence_proposal_id(attempt_id)
    # The commit itself landed (the reply carries its id), the verdict is
    # lost — the exact state a crash between two short transactions leaves.
    assert reply.evidence_commit_id is not None
    assert _proposal_row(db, proposal_id)[6] == "PENDING"
    before = _counts(db)
    assert before["evidence_claim"] == 1
    assert learning.get_evidence_watermark() == 1

    state["dropped"] = False
    retried = LearningController(learning).retry_pending_teaching_evidence()
    assert isinstance(retried, Ok), retried
    assert [(p, str(c)) for p, c in retried.value] == [
        (proposal_id, str(reply.evidence_commit_id))
    ]
    assert _proposal_row(db, proposal_id)[6] == "COMMITTED"
    assert _counts(db) == before
    assert learning.get_evidence_watermark() == 1


def test_a_validation_refusal_is_durable_and_never_retried(
    db: sqlite3.Connection,
    coordinator: ConversationCoordinator,
    learning: SqliteLearningStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Learning's REJECT (DOMAIN_MODEL §18): a proposal whose linked
    opportunity never landed fails validation deterministically, so its
    verdict is durable — and a re-commit is refused instead of looping."""

    original = SqliteLearningStore.record_opportunity

    def dropping(self: SqliteLearningStore, **kwargs: Any):
        # The LOR write is lost (the caller still gets its id back), so the
        # claim's opportunity link cannot resolve at commit time.
        del self, kwargs
        return Ok(LearningOpportunityId("lo-never-written"))

    monkeypatch.setattr(SqliteLearningStore, "record_opportunity", dropping)

    open_moment(coordinator, "cm-p4-reject-open")
    reply = reply_ok(coordinator, make_attempt(CANONICAL_ANSWER), "cm-p4-reject")

    attempt_id = str(reply.attempt_id)
    proposal_id = teaching_evidence_proposal_id(attempt_id)
    assert reply.evidence_commit_id is None
    assert db.execute(
        "SELECT COUNT(*) FROM learning_opportunity_record"
    ).fetchone() == (0,)
    row = _proposal_row(db, proposal_id)
    assert row[6] == "REJECTED"
    assert row[7] == 1
    assert row[10] is None
    assert _counts(db)["evidence_claim"] == 0
    assert learning.get_evidence_watermark() == 0

    monkeypatch.setattr(SqliteLearningStore, "record_opportunity", original)
    refused = learning.commit_teaching_evidence_proposal(proposal_id)
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.CONFLICT
    assert "REJECTED" in refused.error.message
    assert _counts(db)["evidence_claim"] == 0
    retried = LearningController(learning).retry_pending_teaching_evidence()
    assert isinstance(retried, Ok) and retried.value == ()


def test_the_two_id_namespaces_stay_isomorphic(
    db: sqlite3.Connection,
    coordinator: ConversationCoordinator,
) -> None:
    """One attempt → one proposal id and one group id, both derived from the
    attempt id: the teaching side spells the proposal prefix itself (it may
    not import elc.learning) and the committed group keeps the id it always
    had. The reconciliation is this test."""

    assert TEACHING_SIDE_PREFIX == TEACHING_EVIDENCE_PROPOSAL_PREFIX == "tep-"
    assert TEACHING_EVIDENCE_GROUP_PREFIX == "eg-teaching-"
    assert TEACHING_EVIDENCE_PROPOSAL_PREFIX != TEACHING_EVIDENCE_GROUP_PREFIX

    open_moment(coordinator, "cm-p4-ns-open")
    reply = reply_ok(coordinator, make_attempt(CANONICAL_ANSWER), "cm-p4-ns")
    attempt_id = str(reply.attempt_id)

    refs = evidence_proposal_refs_for(
        evaluation=AttemptEvaluation(
            outcome=AttemptOutcome.SUCCESS, confidence=1.0, basis="canonical"
        ),
        attempt_id=attempt_id,
    )
    assert refs == (teaching_evidence_proposal_id(attempt_id),)
    # The ref is a *durable row*, not a naming convention.
    assert _proposal_row(db, refs[0])[6] == "COMMITTED"
    assert _proposal_row(db, refs[0])[1] == attempt_id
    assert db.execute(
        "SELECT evidence_group_id FROM evidence_group"
    ).fetchone() == (teaching_evidence_group_id(attempt_id),)


def test_the_proposal_is_learning_owned_and_never_a_projection_job(
    db: sqlite3.Connection,
    coordinator: ConversationCoordinator,
) -> None:
    """The ownership red line (TASK-…84 红线): the durable proposal is a
    Learning-domain table written by the Learning store only — Learning
    evidence is canonical input, not a rebuildable CP4 projection."""

    open_moment(coordinator, "cm-p4-own-open")
    reply_ok(coordinator, make_attempt(CANONICAL_ANSWER), "cm-p4-own")
    assert db.execute(
        "SELECT COUNT(*) FROM teaching_evidence_proposal WHERE status ="
        " 'COMMITTED'"
    ).fetchone() == (1,)
    # The CP4 work queue is untouched by the whole teaching chain.
    assert db.execute("SELECT COUNT(*) FROM projection_job").fetchone() == (0,)

    markers = (
        "FROM teaching_evidence_proposal",
        "INTO teaching_evidence_proposal",
        "UPDATE teaching_evidence_proposal",
    )
    writers: set[str] = set()
    for path in sorted(SRC_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if any(marker in node.value for marker in markers):
                    writers.add(
                        str(path.relative_to(SRC_ROOT)).replace("\\", "/")
                    )
    assert writers == {"learning/store.py"}, writers


def test_the_refs_of_an_abstain_carry_no_proposal(
    db: sqlite3.Connection,
    coordinator: ConversationCoordinator,
) -> None:
    """Nothing was judged, so nothing is asserted (the pre-P4-0 rule kept):
    an ABSTAIN evaluation carries no ref and writes no proposal row."""

    open_moment(coordinator, "cm-p4-abstain-open")
    reply = reply_ok(coordinator, make_attempt("   "), "cm-p4-abstain")
    assert reply.evaluation_outcome == "ABSTAIN"
    assert reply.opportunity_id is None
    assert reply.evidence_commit_id is None
    assert db.execute("SELECT COUNT(*) FROM attempt_evaluation_record").fetchone() == (
        1,
    )
    assert db.execute(
        "SELECT evidence_proposal_refs FROM attempt_evaluation_record"
    ).fetchone() == ("[]",)
    assert db.execute("SELECT COUNT(*) FROM teaching_evidence_proposal").fetchone() == (
        0,
    )
