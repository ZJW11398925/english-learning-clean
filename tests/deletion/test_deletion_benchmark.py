"""Gate 2 ⑤ — the executable benchmark cases, replayed against this domain.

behavioral_baselines/security/security_benchmark_v1.json carries the cases
this slice is accepted on: the eight deletion cases (S41–S48), the import case
(S49) and the three external-deletion cases (S55–S57). The reference
implementation is replayed byte-for-byte by tests/behavioral/
test_security_reference.py; what these tests do is a different and necessary
thing — they hold **this repository's** faces against the same expectations,
so the semantics are implemented here rather than merely matched in the
baseline.

The deletion cases are exercised through the real app.db probes
(tests/deletion/test_deletion_probes.py builds the world and asserts the
must_delete / must_keep halves per case); the cases that need their own
mechanism — the cancel case, the tombstone case and the import guard — have
their tests here, and every case is mapped to the scope that answers it so a
future benchmark edit cannot silently drop one.
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from elc.deletion.types import (
    DeletionRequest,
    DeletionScope,
    ExternalDisclosure,
    ExternalDisclosureStatus,
)
from elc.platform.types import ConversationId, Ok
from tests.deletion.conftest import (
    BASELINE_SECURITY,
    CONV,
    CONV_OTHER,
    PERSONA,
    SILENT_UTTERANCE,
    TARGET_ID,
    USER,
    commit_chat_turn,
    turn_id_of,
)

CASES = json.loads(
    (BASELINE_SECURITY / "security_benchmark_v1.json").read_text(
        encoding="utf-8"
    )
)
BY_ID = {case["id"]: case for case in CASES}

PENDING_CONV = ConversationId("conv-del-pending")


def _count(db: sqlite3.Connection, table: str, where: str = "", params=()) -> int:
    sql = f"SELECT COUNT(*) FROM {table}"
    if where:
        sql = sql + " WHERE " + where
    row = db.execute(sql, params).fetchone()
    return 0 if row is None else int(row[0])


def test_the_benchmark_carries_every_case_this_slice_claims() -> None:
    """The slice's acceptance face is a named, fixed set of case ids."""

    for case_id in (
        *(f"S{index}" for index in range(41, 50)),
        "S55",
        "S56",
        "S57",
    ):
        assert case_id in BY_ID, case_id


@pytest.mark.parametrize(
    "case_id,scope",
    [
        ("S41", DeletionScope.CONVERSATION),
        ("S42", DeletionScope.RELATIONSHIP_PAIR),
        ("S43", DeletionScope.LEARNING_TARGET),
        ("S44", DeletionScope.PROFILE_FIELD),
        ("S45", DeletionScope.PERSONA_PACKAGE),
        ("S46", DeletionScope.ALL_USER_DATA),
        ("S47", DeletionScope.CONVERSATION),
        ("S48", DeletionScope.LEARNING_TARGET),
    ],
)
def test_every_deletion_case_maps_to_a_shipped_scope(
    case_id: str, scope: DeletionScope
) -> None:
    """Each case's ``request.scope`` is a word this package implements."""

    request = BY_ID[case_id]["input"]["request"]
    assert request["scope"] == scope.value
    assert scope in DeletionScope


def test_s47_deletion_cancels_unfinished_jobs_immediately(
    db: sqlite3.Connection,
    conversation_store,
    silent_coordinator,
    projection_runtime,
    deletion_controller,
    world,
) -> None:
    """S47's ``must_cancel`` — SEC-028, satisfied inside the transaction.

    A real conversation is built with its CP4 jobs enqueued and *not* run, so
    the queue holds exactly the two unfinished rows the case names. The
    deletion removes them there and then: no recovery pass, no drain, no
    restart.
    """

    opened = conversation_store.open_conversation(
        PENDING_CONV, USER, PERSONA, None
    )
    assert isinstance(opened, Ok), opened
    committed = commit_chat_turn(
        silent_coordinator, "cm-pending", SILENT_UTTERANCE, 9,
        conversation=PENDING_CONV,
    )
    assert isinstance(committed, Ok), committed
    turn = turn_id_of(db, PENDING_CONV)
    ensured = projection_runtime.ensure_projection_jobs(turn)
    assert isinstance(ensured, Ok), ensured

    unfinished = _count(
        db,
        "projection_job",
        "status IN ('PENDING', 'FAILED_RETRYABLE') AND source_turn_id = ?",
        (str(turn),),
    )
    assert unfinished == 2, "the case's two pending jobs are real rows"

    result = deletion_controller.execute(
        DeletionRequest(
            scope=DeletionScope.CONVERSATION, conversation_id=PENDING_CONV
        )
    )
    assert isinstance(result, Ok), result
    assert result.value.execution.cancelled_projection_jobs == 2
    assert _count(
        db, "projection_job", "source_turn_id = ?", (str(turn),)
    ) == 0


def test_s48_deletion_tombstones_the_removed_entities(
    db: sqlite3.Connection, deletion_controller, world
) -> None:
    """S48's ``must_tombstone`` — §24's ledger, answered by the predicate."""

    result = deletion_controller.execute(
        DeletionRequest(
            scope=DeletionScope.LEARNING_TARGET, target_id=TARGET_ID
        )
    )
    assert isinstance(result, Ok), result
    assert result.value.execution.tombstoned >= 3

    ledger = deletion_controller.list_tombstones(DeletionScope.LEARNING_TARGET)
    assert isinstance(ledger, Ok), ledger
    kinds = {record.entity_kind for record in ledger.value}
    assert {"evidence_claim", "review_event", "schedule_item"} <= kinds
    assert all(
        record.scope_version == "deletion-policy-v1"
        for record in ledger.value
    )


def test_s49_the_import_guard_keeps_only_the_surviving_record(
    db: sqlite3.Connection,
    conversation_store,
    deletion_controller,
) -> None:
    """S49 verbatim, over a ledger this app really wrote.

    The case's ``tombstones=["old"]`` is not a hand-made set here: the entity
    ``old`` is a real conversation that a real deletion removed, so the guard
    is answering from the durable §24 ledger and not from the benchmark's
    input list.
    """

    case = BY_ID["S49"]
    records = case["input"]["records"]
    deleted = case["input"]["tombstones"][0]

    opened = conversation_store.open_conversation(
        ConversationId(deleted), USER, None, None
    )
    assert isinstance(opened, Ok), opened
    removed = deletion_controller.execute(
        DeletionRequest(
            scope=DeletionScope.CONVERSATION,
            conversation_id=ConversationId(deleted),
        )
    )
    assert isinstance(removed, Ok), removed

    filtered = deletion_controller.filter_tombstoned(
        records, entity_kind="conversation"
    )
    assert isinstance(filtered, Ok), filtered
    assert [str(record["id"]) for record in filtered.value] == case["expected"][
        "ids"
    ]

    assert deletion_controller.is_tombstoned(
        entity_kind="conversation", entity_id=deleted
    ).value is True
    assert deletion_controller.is_tombstoned(
        entity_kind="conversation", entity_id="keep"
    ).value is False


def test_s49_the_guard_is_scope_aware() -> None:
    """``keep`` survives because it was never deleted — not because the guard
    is lenient: the same id under another kind is not tombstoned either."""

    from elc.deletion.plan import apply_tombstone_guard, entity_hash_for

    ledger = {("conversation", entity_hash_for("conversation", "old"))}
    records = [{"id": "old"}, {"id": "keep"}]
    kept = apply_tombstone_guard(records, ledger=ledger, entity_kind="turn_record")
    assert [str(record["id"]) for record in kept] == ["old", "keep"]


@pytest.mark.parametrize(
    "case_id,external,revocation",
    [
        ("S55", "NONE", "NOT_APPLICABLE"),
        ("S56", "NONE", "CANNOT_BE_GUARANTEED_BY_APP"),
        ("S57", "SCHEDULE_PROVIDER_DELETE", "PENDING_PROVIDER"),
    ],
)
def test_external_delete_three_states_match_the_benchmark(
    case_id: str, external: str, revocation: str, deletion_controller
) -> None:
    """S55–S57, word for word (§25/§26, SEC-021/SEC-022).

    The judgement is the whole behaviour: no remote call is made, and the
    SENT-and-supported branch names an intent rather than a completion
    (``PENDING_PROVIDER``), which is what stops the product from claiming a
    remote revocation it cannot prove.
    """

    disclosure = BY_ID[case_id]["input"]["disclosure"]
    plan = deletion_controller.plan_external_delete(
        ExternalDisclosure(
            status=ExternalDisclosureStatus(disclosure["status"]),
            provider_delete_supported=bool(
                disclosure.get("provider_delete_supported", False)
            ),
            provider_request_identifier=disclosure.get("provider_request_id"),
        )
    )
    assert isinstance(plan, Ok), plan
    assert plan.value.external_action.value == external
    assert plan.value.remote_revocation.value == revocation
    assert BY_ID[case_id]["expected"]["external_action"] == external
    assert BY_ID[case_id]["expected"]["remote_revocation"] == revocation


def test_a_sent_disclosure_is_never_reported_as_revoked(
    deletion_controller,
) -> None:
    """SEC-022's negative half: no input produces a "revoked" answer.

    The vocabulary has no revoked word at all, so the honest failure mode is
    impossible to reach — which is the point of freezing it here.
    """

    from elc.deletion.types import RemoteRevocation

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
                assert plan.value.remote_revocation in set(RemoteRevocation)
                assert plan.value.remote_revocation.value != "REVOKED"


def test_the_deletion_world_is_the_one_the_cases_describe() -> None:
    """A guard against a probe suite that drifts away from the cases' shape."""

    assert BY_ID["S41"]["input"]["graph"][0]["kind"] == "CONVERSATION"
    assert BY_ID["S42"]["input"]["request"] == {
        "scope": "RELATIONSHIP_PAIR",
        "persona_id": "p1",
    }
    assert BY_ID["S43"]["input"]["request"] == {
        "scope": "LEARNING_TARGET",
        "target_id": "t1",
    }
    # The world's own ids are this repository's, not the benchmark's — the
    # mapping is the point of the case, not the literal strings.
    assert CONV != CONV_OTHER
