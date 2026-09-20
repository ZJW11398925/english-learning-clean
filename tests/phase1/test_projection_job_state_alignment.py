"""F3 (DEC-OPI-d7937fd7.19) — ProjectionJobState aligns docs/DATA_MODEL.md
§22.1 word for word, and matches the projection_job status CHECK constraint
in migrations/0002_conversation_core.sql (correcting the Phase 0 three-value
placeholder PENDING/COMPLETED/FAILED)."""

from __future__ import annotations

from elc.platform.db.connection import DEFAULT_MIGRATIONS_DIR
from elc.runtime.types import ProjectionJobState

#: docs/DATA_MODEL.md §22.1 status block, word for word, in order.
DM221_PROJECTION_JOB_STATES = (
    "PENDING",
    "RUNNING",
    "COMMITTED",
    "FAILED_RETRYABLE",
    "REJECTED",
)


def test_projection_job_state_is_dm221_five_values() -> None:
    """VAL ①-style vocabulary pin: §22.1 five values, same order, no Phase 0
    leftovers (the COMPLETED/FAILED placeholders are gone)."""

    assert [state.value for state in ProjectionJobState] == list(
        DM221_PROJECTION_JOB_STATES
    )
    for legacy in ("COMPLETED", "FAILED"):
        assert not hasattr(ProjectionJobState, legacy)


def test_projection_job_state_matches_migration_check() -> None:
    """The durable projection_job status CHECK (migrations/0002) pins the
    same five words in the same order — enum and schema cannot drift apart
    silently (static read of the SQL text, per the review fix scope)."""

    script = (DEFAULT_MIGRATIONS_DIR / "0002_conversation_core.sql").read_text(
        encoding="utf-8"
    )
    start = script.index("CREATE TABLE IF NOT EXISTS projection_job (")
    end = script.index(";", start)
    block = script[start:end]

    cursor = 0
    for state in DM221_PROJECTION_JOB_STATES:
        at = block.index(f"'{state}'", cursor)
        cursor = at + len(f"'{state}'")
