"""Gate 2 ⑤ — SEC-017…SEC-028, one executable check per invariant.

The contract's §33 lists thirty invariants; twelve of them (SEC-017…SEC-028)
are the deletion block, and this module is where each one has a test that
would fail if the invariant stopped holding. The grouping is deliberate — an
invariant with no test is a paragraph, and a paragraph is what this slice was
asked to replace.

Where an invariant has **no storage to act on** in V1 (SEC-020's indexes and
embeddings), the test pins the absence rather than inventing a stand-in, and
the same is true of the import face (SEC-024) and the remote revocation
(SEC-022). A registered gap is checkable; a simulated one is not.
"""

from __future__ import annotations

import sqlite3

import pytest

from elc.deletion.types import (
    DeletionRequest,
    DeletionScope,
    ExternalDisclosure,
    ExternalDisclosureStatus,
    RemoteRevocation,
)
from elc.platform.types import ConversationId, Err, Ok
from elc.runtime.types import ProjectionJobState
from tests.deletion.conftest import (
    CONV,
    MAIN_MEMORY,
    PERSONA,
    SILENT_UTTERANCE,
    TARGET_ID,
    USER,
    commit_chat_turn,
    turn_id_of,
)

RUNNING_CONV = ConversationId("conv-del-running")


def _count(db: sqlite3.Connection, table: str, where: str = "", params=()) -> int:
    sql = f"SELECT COUNT(*) FROM {table}"
    if where:
        sql = sql + " WHERE " + where
    row = db.execute(sql, params).fetchone()
    return 0 if row is None else int(row[0])


def _columns(db: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in db.execute(f"PRAGMA table_info({table})")}


# -- SEC-017 -----------------------------------------------------------------


def test_sec_017_long_term_derived_state_carries_provenance(
    db: sqlite3.Connection,
) -> None:
    """Every long-term derived row can answer "which sources?".

    Checked as a column fact per table rather than as a promise: a derived
    object that lost its provenance column would fail here.
    """

    assert {"source_turn_id", "source_turn_ids", "provenance_refs"} <= _columns(
        db, "relationship_memory"
    )
    assert {"source_turn_id", "conversation_id"} <= _columns(
        db, "evidence_claim"
    )
    assert {"source_turn_id", "conversation_id"} <= _columns(
        db, "evidence_group"
    )
    assert {
        "conversation_id",
        "source_turn_sequence_start",
        "source_turn_sequence_end",
    } <= _columns(db, "episode")
    assert "source_learning_watermark" in _columns(db, "schedule_item")


def test_sec_017_registers_the_one_table_that_cannot_answer_it(
    db: sqlite3.Connection,
) -> None:
    """``user_profile`` is the registered exception, not a silent one.

    §17's requirement and §5.1's frozen column set conflict for profile
    facts; this cut adds no column (§5.1 is frozen) and the fail-closed
    behaviour is the compensation. The assertion is the registration itself.
    """

    assert not ({"source_ids", "provenance"} & _columns(db, "user_profile"))


# -- SEC-018 / SEC-019 -------------------------------------------------------


def test_sec_018_deleting_a_source_deletes_or_rebuilds_solely_derived_data(
    db: sqlite3.Connection, world, deletion_controller
) -> None:
    """A conversation deletion reports both halves: removals and rebuilds."""

    before = _count(db, "evidence_claim", "conversation_id = ?", (str(CONV),))
    assert before >= 1, "the chain produced conversation-sourced evidence"

    result = deletion_controller.execute(
        DeletionRequest(
            scope=DeletionScope.CONVERSATION, conversation_id=CONV
        )
    )
    assert isinstance(result, Ok), result
    outcome = result.value
    deleted_tables = {tally.table for tally in outcome.execution.tallies}
    assert "evidence_claim" in deleted_tables
    assert "relationship_memory" in deleted_tables
    # And the views that survived a partial source are rebuilt, not dropped.
    assert all(
        attempt.ok
        for attempt in outcome.rebuilds
        if attempt.kind in {"LEARNER_STATE", "SCHEDULE_ITEM"}
    )


def test_sec_019_a_conversation_deletion_removes_its_solely_sourced_evidence(
    db: sqlite3.Connection, world, deletion_controller
) -> None:
    result = deletion_controller.execute(
        DeletionRequest(
            scope=DeletionScope.CONVERSATION, conversation_id=CONV
        )
    )
    assert isinstance(result, Ok), result
    assert _count(
        db, "evidence_claim", "conversation_id = ?", (str(CONV),)
    ) == 0
    # The sibling conversation's evidence is untouched.
    assert _count(
        db,
        "evidence_claim",
        "conversation_id = ?",
        (str(world.conversations["other"]),),
    ) >= 1


# -- SEC-020 -----------------------------------------------------------------


def test_sec_020_registers_that_v1_has_no_index_or_embedding_store(
    db: sqlite3.Connection,
) -> None:
    """§18's "indexes/embeddings deleted or rebuilt" has no storage here.

    The check is the absence itself — a later cut that lands a retrieval index
    fails this test and has to classify its table in the sweep sets, which is
    the point.
    """

    tables = {
        str(row[0])
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert not [
        table
        for table in tables
        if any(
            marker in table
            for marker in ("index", "embedding", "vector", "search_cache")
        )
    ]


# -- SEC-021 / SEC-022 -------------------------------------------------------


def test_sec_021_and_022_the_actions_partition_by_transmission(
    db: sqlite3.Connection, world, deletion_controller
) -> None:
    """Every action of the conversation is accounted for, one way or the other.

    ``cancelled`` counts the never-transmitted ones (§25's "cancel before
    transmission"); ``sent`` counts the ones that left the app (§26 — whose
    remote fate the app may not claim). The two must add up to what the
    conversation held, and neither may be silently dropped.
    """

    actions = _count(
        db,
        "generation_action_intent",
        "turn_id IN (SELECT turn_id FROM turn_record WHERE conversation_id = ?)",
        (str(CONV),),
    )
    assert actions >= 1, "the real turn produced a generation action"

    result = deletion_controller.execute(
        DeletionRequest(
            scope=DeletionScope.CONVERSATION, conversation_id=CONV
        )
    )
    assert isinstance(result, Ok), result
    execution = result.value.execution
    assert (
        execution.cancelled_provider_actions + execution.sent_provider_actions
        == actions
    )


def test_sec_022_no_answer_claims_a_remote_revocation(
    deletion_controller,
) -> None:
    """Nothing this app can say means "the third party's copy is gone".

    The vocabulary has no such word, and the two sent branches are the two
    honest answers §26 allows: explicitly unguaranteeable, or pending.
    """

    unsent = {
        ExternalDisclosureStatus.NOT_SENT,
        ExternalDisclosureStatus.QUEUED,
    }
    for status in ExternalDisclosureStatus:
        for supported in (False, True):
            for identifier in (None, "req-1"):
                plan = deletion_controller.plan_external_delete(
                    ExternalDisclosure(
                        status=status,
                        provider_delete_supported=supported,
                        provider_request_identifier=identifier,
                    )
                )
                assert isinstance(plan, Ok), plan
                answer = plan.value.remote_revocation
                assert answer in set(RemoteRevocation)
                if status in unsent:
                    assert answer is RemoteRevocation.NOT_APPLICABLE
                else:
                    assert answer in {
                        RemoteRevocation.CANNOT_BE_GUARANTEED_BY_APP,
                        RemoteRevocation.PENDING_PROVIDER,
                    }


# -- SEC-023 / SEC-024 -------------------------------------------------------


def test_sec_023_the_ledger_holds_no_deleted_plaintext(
    db: sqlite3.Connection, world, deletion_controller
) -> None:
    """The strongest form: search every text column of the ledger.

    The deleted strings are real ones — a relationship memory's content and a
    user turn's raw text — and neither may appear anywhere in
    ``deletion_tombstone`` after the deletion that removed them.
    """

    transcript = str(
        db.execute(
            "SELECT raw_content FROM user_turn WHERE conversation_id = ?",
            (str(CONV),),
        ).fetchone()[0]
    )
    result = deletion_controller.execute(
        DeletionRequest(
            scope=DeletionScope.CONVERSATION, conversation_id=CONV
        )
    )
    assert isinstance(result, Ok), result
    assert _count(db, "deletion_tombstone") > 0

    rows = db.execute("SELECT * FROM deletion_tombstone").fetchall()
    blob = " ".join(
        str(value) for row in rows for value in tuple(row) if value is not None
    )
    assert MAIN_MEMORY not in blob
    assert transcript not in blob
    assert str(CONV) not in blob


def test_sec_024_tombstones_are_written_and_idempotent(
    db: sqlite3.Connection, world, deletion_controller
) -> None:
    first = deletion_controller.execute(
        DeletionRequest(
            scope=DeletionScope.CONVERSATION, conversation_id=CONV
        )
    )
    assert isinstance(first, Ok), first
    ledger = deletion_controller.list_tombstones()
    assert isinstance(ledger, Ok), ledger
    assert ledger.value

    # A second run touches nothing (the conversation is gone) and mints no
    # second ledger row for the same entity.
    second = deletion_controller.execute(
        DeletionRequest(
            scope=DeletionScope.CONVERSATION, conversation_id=CONV
        )
    )
    assert isinstance(second, Ok), second
    assert second.value.execution.tombstoned == 0
    again = deletion_controller.list_tombstones()
    assert again.value == ledger.value


def test_sec_024_the_guard_is_the_only_importer_of_tombstones() -> None:
    """V1 ships no import face — registered rather than implied.

    The guard exists so the semantics are executable now; a test asserts that
    nothing outside this package consumes it, which is what "no import path
    yet" means in code. The scan looks for the *guard's names*, not for any
    ``elc.deletion`` import: the platform registry legitimately imports this
    package's record type (it registers the tombstone as a canonical object).
    """

    import ast

    from tests.conftest import SRC_ROOT

    guard_names = {"apply_tombstone_guard", "filter_tombstoned"}
    importers: list[str] = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        if path.parts[-2] == "deletion":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name in guard_names:
                        importers.append(f"{path.name}: {alias.name}")
    assert not importers, importers


# -- SEC-025 -----------------------------------------------------------------


def test_sec_025_all_user_data_keeps_the_schema_and_the_ledger(
    db: sqlite3.Connection, world, deletion_controller
) -> None:
    result = deletion_controller.execute(
        DeletionRequest(scope=DeletionScope.ALL_USER_DATA)
    )
    assert isinstance(result, Ok), result
    assert _count(db, "schema_meta") >= 2
    assert _count(db, "schema_migrations") == 14
    assert _count(db, "runtime_epoch") == 1
    assert _count(db, "deletion_tombstone") > 0


# -- SEC-026 / SEC-027 -------------------------------------------------------


def test_sec_026_learning_deletion_leaves_the_pair_alone(
    db: sqlite3.Connection, world, deletion_controller
) -> None:
    before = _count(db, "relationship_memory")
    result = deletion_controller.execute(
        DeletionRequest(
            scope=DeletionScope.LEARNING_TARGET, target_id=TARGET_ID
        )
    )
    assert isinstance(result, Ok), result
    assert _count(db, "relationship_memory") == before
    assert _count(db, "conversation") == 3


def test_sec_027_relationship_deletion_leaves_learning_alone(
    db: sqlite3.Connection, world, deletion_controller
) -> None:
    """Both Learning halves are compared against what they held *before*.

    The target-state half read ``_count(…) == _count(…)`` — a self-comparison
    that can never fail — until the Gate 2 review caught it (F1). It is now
    the same before/after shape as the evidence half, with a non-vacuity leg
    so a world that stopped producing materialized state fails here instead of
    making the equality trivially true.
    """

    before = _count(db, "evidence_claim")
    before_state = _count(db, "learner_target_state")
    assert before_state >= 1, "the silent chain materialized target state"
    result = deletion_controller.execute(
        DeletionRequest(
            scope=DeletionScope.RELATIONSHIP_PAIR, persona_id=PERSONA
        )
    )
    assert isinstance(result, Ok), result
    assert _count(db, "evidence_claim") == before
    assert _count(db, "learner_target_state") == before_state


# -- SEC-028 -----------------------------------------------------------------


def test_sec_028_a_running_job_can_no_longer_land_after_the_deletion(
    db: sqlite3.Connection,
    conversation_store,
    silent_coordinator,
    projection_store,
    projection_runtime,
    deletion_controller,
    world,
) -> None:
    """The immediacy rule, from the in-flight side.

    A claimed (RUNNING) job whose source conversation is deleted must not be
    completable afterwards — the row leaves with its turn, and the durable
    machine refuses a completion for a job it no longer holds.
    """

    opened = conversation_store.open_conversation(
        RUNNING_CONV, USER, PERSONA, None
    )
    assert isinstance(opened, Ok), opened
    committed = commit_chat_turn(
        silent_coordinator,
        "cm-running",
        SILENT_UTTERANCE,
        11,
        conversation=RUNNING_CONV,
    )
    assert isinstance(committed, Ok), committed
    turn = turn_id_of(db, RUNNING_CONV)
    ensured = projection_runtime.ensure_projection_jobs(turn)
    assert isinstance(ensured, Ok), ensured
    job_id = ensured.value[0]
    claimed = projection_store.claim_projection(job_id, base_version=None)
    assert isinstance(claimed, Ok), claimed
    assert claimed.value.status is ProjectionJobState.RUNNING

    result = deletion_controller.execute(
        DeletionRequest(
            scope=DeletionScope.CONVERSATION, conversation_id=RUNNING_CONV
        )
    )
    assert isinstance(result, Ok), result

    assert _count(
        db, "projection_job", "projection_id = ?", (str(job_id),)
    ) == 0
    refused = projection_store.complete_projection(job_id)
    assert isinstance(refused, Err), refused


@pytest.mark.parametrize("scope", sorted(s.value for s in DeletionScope))
def test_every_scope_is_reachable_and_refuses_a_keyless_request(
    scope: str, deletion_controller, db: sqlite3.Connection
) -> None:
    """No scope silently deletes everything for a missing key.

    A request without the key its scope needs is a ``VALIDATION_FAILED`` with
    zero writes — the failure mode this check exists for is a typo that turns
    "delete this conversation" into "delete nothing" or, worse, into a broader
    sweep.
    """

    value = DeletionScope(scope)
    request = DeletionRequest(scope=value)
    result = deletion_controller.execute(request)
    if value in {
        DeletionScope.CONVERSATION,
        DeletionScope.LEARNING_TARGET,
        DeletionScope.RELATIONSHIP_PAIR,
        DeletionScope.PROFILE_FIELD,
    }:
        assert isinstance(result, Err), (scope, result)
        assert _count(db, "deletion_tombstone") == 0
    else:
        assert isinstance(result, Ok), (scope, result)
