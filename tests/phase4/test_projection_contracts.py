"""P4-0 ④ — the CP4 projection contracts (semantics fixed, runtime is P4-2).

This slice lands contracts, not a runtime: the ``projection_job`` table and
its §22.1 states already exist (migrations/0002), and the semantics the P4-2
execution must honor are adjudicated in the ``elc.runtime.types`` module
docstring. The pins here are exactly that:

- every clause of the contract is present in the contract text (so a later
  edit cannot quietly drop one);
- ``enqueue_projection`` still raises, naming P4-2 — no pretend runtime;
- the whole teaching-evidence chain leaves ``projection_job`` empty: a
  Learning proposal is canonical input, never a CP4 projection job.
"""

from __future__ import annotations

import sqlite3

import pytest

from elc.platform.types import TurnId
from elc.runtime.controller import ConversationCoordinator, RuntimeOrchestrator
from elc.runtime.types import (
    ProjectionJobRecord,
    ProjectionJobState,
)
from tests.conftest import SRC_ROOT

from .conftest import CANONICAL_ANSWER, open_moment, reply_ok
from .conftest import attempt as make_attempt

#: One marker per adjudicated clause of the P4-0 ④ contract (the module
#: docstring of elc.runtime.types is where it lives; the markers are the
#: phrases the clause is stated with).
CONTRACT_MARKERS = (
    "stable projection_id",
    "idempotent enqueue",
    "PENDING → RUNNING → COMMITTED",
    "FAILED_RETRYABLE → REJECTED",
    "source_turn_slice_hash",
    "base_domain_version",
    "ConversationCoordinatorLease",
    "never rolls back the transcript",
    "never blocks the next turn",
    "ensure_projection_job",
)


def _normalized_source() -> str:
    """The runtime contract text with line wrapping neutralized: the pin is
    about the clauses, not about where the formatter broke a line."""

    source = (SRC_ROOT / "runtime" / "types.py").read_text(encoding="utf-8")
    return " ".join(source.split()).lower()


def test_every_cp4_contract_clause_is_recorded() -> None:
    text = _normalized_source()
    missing = [marker for marker in CONTRACT_MARKERS if marker.lower() not in text]
    assert not missing, missing


def test_the_learning_proposal_is_not_a_projection_job() -> None:
    """The ownership sentence of the contract, pinned in the same text: a
    teaching-evidence proposal is canonical Learning evidence, deliberately
    not a projection_job row."""

    text = _normalized_source()
    assert "teaching_evidence_proposal" in text
    assert "not a projection_job row" in text


def test_enqueue_projection_is_still_a_raise(db: sqlite3.Connection) -> None:
    """No fake runtime: the enqueue face names the phase that implements it,
    and nothing reaches the durable projection queue."""

    orchestrator = RuntimeOrchestrator()
    job = ProjectionJobRecord(
        projection_job_id="pr-p4-0",
        conversation_id="conv-p4",
        source_turn_id=TurnId("turn-p4-0"),
        projection_type="RELATIONSHIP",
        source_version="v1",
        state=ProjectionJobState.PENDING,
    )
    with pytest.raises(NotImplementedError) as excinfo:
        orchestrator.enqueue_projection(job)
    assert "P4-2" in str(excinfo.value)
    assert db.execute("SELECT COUNT(*) FROM projection_job").fetchone() == (0,)


def test_the_teaching_chain_leaves_the_projection_queue_empty(
    db: sqlite3.Connection,
    coordinator: ConversationCoordinator,
) -> None:
    """The red line (TASK-…84 红线): Learning evidence never rides the CP4
    work queue — the durable proposal exists while projection_job stays
    empty, in the same database."""

    open_moment(coordinator, "cm-p4-proj-open")
    reply_ok(coordinator, make_attempt(CANONICAL_ANSWER), "cm-p4-proj")
    assert db.execute(
        "SELECT COUNT(*) FROM teaching_evidence_proposal"
    ).fetchone() == (1,)
    assert db.execute("SELECT COUNT(*) FROM projection_job").fetchone() == (0,)
