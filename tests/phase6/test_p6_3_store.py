"""P6-3 ③.3 — the constraint store: write discipline, the flag transfer, and the
three reads.

The claims this file pins, in the order the store states them:

- **the content write is append-first** (§9 has no version column): the same
  ``constraint_id`` with the same content is an idempotent replay that writes
  nothing, and any differing column — ``active`` included — is a ``CONFLICT``
  with the durable row left byte for byte as it was;
- **the flag has one face** (:meth:`set_planner_constraint_active`): it moves
  ``active`` and nothing else, re-transferring the current value writes
  nothing, and an unknown id is ``NOT_FOUND``;
- **the active reads compare instants**, not bytes: ``active`` ∧
  ``starts_at <= as_of`` ∧ (``expires_at`` is NULL ∨ ``as_of <= expires_at``),
  both boundaries inclusive, ordered by ``constraint_id``, with an empty /
  unparseable / naive ``as_of`` refused as ``VALIDATION_FAILED`` and a message
  that carries no bare exception text;
- **the target read adds one leg**: a NULL target leg is not target-limited
  and applies to every target, a verbatim-matching pair applies to this one,
  and a half-declared leg applies to none;
- **fencing**: every write is refused by a stale store, and every read is
  read-only (proved by ``Connection.total_changes``).

The rows are produced exclusively through the shipped faces — this suite
writes no hand-made SQL row, and no fixture supply is imported.
"""

from __future__ import annotations

import dataclasses
import sqlite3

import pytest

from elc.platform.types import DomainErrorCode, Err, Ok, TargetId
from elc.user_config.controller import UserConfigController
from elc.user_config.store import SqliteUserConfigStore, StaleStoreEpochError
from elc.user_config.types import (
    PlannerConstraint,
    PlannerConstraintScope,
    PlannerConstraintType,
)

from .conftest import (
    AS_OF,
    CONSTRAINT_END,
    CONSTRAINT_ID,
    CONSTRAINT_START,
    TARGET_ID,
    TARGET_TYPE,
    planner_constraint,
)

OTHER_CONSTRAINT_ID = "pc-2"


@pytest.fixture()
def controller(user_config_store: SqliteUserConfigStore) -> UserConfigController:
    return UserConfigController(user_config_store)


def _raw(db: sqlite3.Connection, constraint_id: str) -> tuple[object, ...]:
    """The durable row as the database holds it (the unchanged-check basis)."""

    row = db.execute(
        "SELECT constraint_id, target_type, target_id, constraint_type, scope,"
        " starts_at, expires_at, created_from_turn_id, active"
        " FROM planner_constraint WHERE constraint_id = ?",
        (constraint_id,),
    ).fetchone()
    assert row is not None, f"constraint {constraint_id} is not durable"
    return tuple(row)


def _ids(result: Ok[tuple[PlannerConstraint, ...]]) -> list[str]:
    return [constraint.constraint_id for constraint in result.value]


# -- ① the content write -----------------------------------------------------


def test_a_recorded_constraint_reads_back_byte_for_byte(
    user_config_store: SqliteUserConfigStore,
) -> None:
    written = planner_constraint(
        target_type=TARGET_TYPE,
        target_id=TARGET_ID,
        expires_at=None,
        scope=PlannerConstraintScope.UNTIL_USER_REENABLES,
    )
    result = user_config_store.record_planner_constraint(written)
    assert isinstance(result, Ok), result
    assert result.value == written
    assert user_config_store.get_planner_constraint(CONSTRAINT_ID) == Ok(written)


def test_the_table_starts_empty(db: sqlite3.Connection) -> None:
    assert db.execute("SELECT COUNT(*) FROM planner_constraint").fetchone() == (
        0,
    )


def test_recording_the_same_content_twice_writes_nothing(
    db: sqlite3.Connection, user_config_store: SqliteUserConfigStore
) -> None:
    """The idempotent replay (the crash-retry face): same id, same content —
    the durable row comes back and no statement touches a row."""

    written = planner_constraint()
    first = user_config_store.record_planner_constraint(written)
    assert isinstance(first, Ok)
    before = db.total_changes
    again = user_config_store.record_planner_constraint(written)
    assert isinstance(again, Ok)
    assert again.value == first.value
    assert db.total_changes == before


#: The eight non-identity columns, each with a differing value and the refusal
#: it earns. ``active`` is in the list on purpose: the content face refuses a
#: flag change too. ``created_from_turn_id`` earns ``NOT_FOUND`` rather than
#: ``CONFLICT`` because the write face pre-checks the foreign key before it
#: looks at the durable row — the ordering is itself pinned below.
DIFFERING_COLUMNS: dict[str, tuple[object, DomainErrorCode]] = {
    "target_type": ("CAPABILITY", DomainErrorCode.CONFLICT),
    "target_id": (
        TargetId("cap-ref-ask-clarification"),
        DomainErrorCode.CONFLICT,
    ),
    "constraint_type": (
        PlannerConstraintType.SUPPRESS_REVIEW,
        DomainErrorCode.CONFLICT,
    ),
    "scope": (
        PlannerConstraintScope.UNTIL_USER_REENABLES,
        DomainErrorCode.CONFLICT,
    ),
    "starts_at": ("2026-09-21T09:00:00+00:00", DomainErrorCode.CONFLICT),
    "expires_at": ("2026-09-30T09:00:00+00:00", DomainErrorCode.CONFLICT),
    "created_from_turn_id": ("t-does-not-exist", DomainErrorCode.NOT_FOUND),
    "active": (False, DomainErrorCode.CONFLICT),
}


@pytest.mark.parametrize("column", sorted(DIFFERING_COLUMNS))
def test_a_differing_column_is_refused(
    db: sqlite3.Connection,
    user_config_store: SqliteUserConfigStore,
    column: str,
) -> None:
    """One claim per column: §9's missing version stamp means the content face
    cannot rewrite an existing id, so a difference of any kind is refused —
    and the durable row is untouched."""

    value, expected = DIFFERING_COLUMNS[column]
    written = planner_constraint()
    assert isinstance(user_config_store.record_planner_constraint(written), Ok)
    durable_row = _raw(db, CONSTRAINT_ID)
    changed = dataclasses.replace(written, **{column: value})
    refused = user_config_store.record_planner_constraint(changed)
    assert isinstance(refused, Err), refused
    assert refused.error.code is expected
    # The refusal names what the caller has to act on: the constraint for a
    # content conflict, the missing turn for the foreign-key probe.
    if expected is DomainErrorCode.CONFLICT:
        assert CONSTRAINT_ID in refused.error.message
    else:
        assert str(value) in refused.error.message
    assert _raw(db, CONSTRAINT_ID) == durable_row


def test_the_foreign_key_probe_runs_before_the_replay_check(
    db: sqlite3.Connection, user_config_store: SqliteUserConfigStore
) -> None:
    """The ordering the row above leans on, stated on its own: a constraint
    that is both a content change *and* cites a turn that does not exist comes
    back as ``NOT_FOUND`` (the pre-check), not as ``CONFLICT``. Either way
    nothing is written — and the message names the turn, which is the half a
    caller can act on."""

    written = planner_constraint()
    assert isinstance(user_config_store.record_planner_constraint(written), Ok)
    durable_row = _raw(db, CONSTRAINT_ID)
    both = dataclasses.replace(
        written,
        constraint_type=PlannerConstraintType.JUST_CHAT,
        created_from_turn_id="t-absent",
    )
    refused = user_config_store.record_planner_constraint(both)
    assert isinstance(refused, Err), refused
    assert refused.error.code is DomainErrorCode.NOT_FOUND
    assert "t-absent" in refused.error.message
    assert _raw(db, CONSTRAINT_ID) == durable_row


def test_the_content_face_refuses_a_differing_active_flag(
    db: sqlite3.Connection, user_config_store: SqliteUserConfigStore
) -> None:
    """The R6 exception, stated on its own: ``active`` is content here, so an
    inbound flag that differs is refused — the flag moves through
    ``set_planner_constraint_active`` and nowhere else."""

    written = planner_constraint(active=True)
    assert isinstance(user_config_store.record_planner_constraint(written), Ok)
    refused = user_config_store.record_planner_constraint(
        dataclasses.replace(written, active=False)
    )
    assert isinstance(refused, Err), refused
    assert refused.error.code is DomainErrorCode.CONFLICT
    assert "set_planner_constraint_active" in refused.error.message
    assert _raw(db, CONSTRAINT_ID)[-1] == 1


def test_the_refusal_names_the_append_first_rule(
    user_config_store: SqliteUserConfigStore,
) -> None:
    written = planner_constraint()
    assert isinstance(user_config_store.record_planner_constraint(written), Ok)
    refused = user_config_store.record_planner_constraint(
        dataclasses.replace(written, starts_at="2026-09-21T09:00:00+00:00")
    )
    assert isinstance(refused, Err)
    assert "constraint_id" in refused.error.message
    assert "§1.3" in refused.error.message


# -- ② the two pre-checks ----------------------------------------------------


def test_an_unknown_turn_is_not_found(
    db: sqlite3.Connection, user_config_store: SqliteUserConfigStore
) -> None:
    """§9's ``created_from_turn_id?`` is a real foreign key to
    ``turn_record``: a turn that does not exist is this domain's ``NOT_FOUND``,
    not a sqlite integrity error."""

    before = db.total_changes
    refused = user_config_store.record_planner_constraint(
        planner_constraint(created_from_turn="t-absent")
    )
    assert isinstance(refused, Err), refused
    assert refused.error.code is DomainErrorCode.NOT_FOUND
    assert "t-absent" in refused.error.message
    assert db.total_changes == before
    assert db.execute("SELECT COUNT(*) FROM planner_constraint").fetchone() == (
        0,
    )


def test_the_not_found_message_carries_no_sqlite_text(
    user_config_store: SqliteUserConfigStore,
) -> None:
    """The p6-1 F-2 rule: a ``DomainError`` message is this domain's
    vocabulary, so sqlite's own words never travel."""

    refused = user_config_store.record_planner_constraint(
        planner_constraint(created_from_turn="t-absent")
    )
    assert isinstance(refused, Err)
    lowered = refused.error.message.lower()
    for leak in ("sqlite", "integrityerror", "foreign key constraint failed"):
        assert leak not in lowered, leak


def test_a_real_turn_is_accepted(
    db: sqlite3.Connection,
    user_config_store: SqliteUserConfigStore,
    conversation,
    silent_coordinator,
) -> None:
    """The positive half: a constraint may cite a turn the shipped chain
    actually wrote (the foreign key is reachable in the real world, not only
    in a refusal)."""

    from .conftest import SILENT_UTTERANCE, commit_chat_turn

    del conversation
    commit_chat_turn(
        silent_coordinator, "cm-p6-3-constraint-turn", SILENT_UTTERANCE, 1
    )
    turn_id = str(
        db.execute("SELECT turn_id FROM turn_record").fetchone()[0]
    )
    written = planner_constraint(created_from_turn=turn_id)
    result = user_config_store.record_planner_constraint(written)
    assert isinstance(result, Ok), result
    assert str(result.value.created_from_turn_id) == turn_id


@pytest.mark.parametrize(
    "target_type", ["GOAL", "resource", "", "TARGET"]
)
def test_an_unknown_target_type_is_refused(
    db: sqlite3.Connection,
    user_config_store: SqliteUserConfigStore,
    target_type: str,
) -> None:
    """The migration's CHECK, said in the caller's vocabulary: only §9's two
    words (RESOURCE / CAPABILITY) may be written, case-sensitively."""

    before = db.total_changes
    refused = user_config_store.record_planner_constraint(
        planner_constraint(target_type=target_type, target_id=TARGET_ID)
    )
    assert isinstance(refused, Err), refused
    assert refused.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "RESOURCE" in refused.error.message
    assert db.total_changes == before


@pytest.mark.parametrize("target_type", ["RESOURCE", "CAPABILITY"])
def test_the_two_canonical_target_types_are_accepted(
    user_config_store: SqliteUserConfigStore, target_type: str
) -> None:
    result = user_config_store.record_planner_constraint(
        planner_constraint(target_type=target_type, target_id=TARGET_ID)
    )
    assert isinstance(result, Ok), result


# -- ③ the flag transfer -----------------------------------------------------


@pytest.mark.parametrize("start_active", [True, False])
def test_the_flag_moves(
    db: sqlite3.Connection,
    user_config_store: SqliteUserConfigStore,
    start_active: bool,
) -> None:
    written = planner_constraint(active=start_active)
    assert isinstance(user_config_store.record_planner_constraint(written), Ok)
    moved = user_config_store.set_planner_constraint_active(
        CONSTRAINT_ID, not start_active
    )
    assert isinstance(moved, Ok), moved
    assert moved.value.active is (not start_active)
    assert _raw(db, CONSTRAINT_ID)[-1] == (0 if start_active else 1)
    assert user_config_store.get_planner_constraint(CONSTRAINT_ID) == Ok(
        moved.value
    )


def test_the_transfer_changes_no_other_column(
    db: sqlite3.Connection, user_config_store: SqliteUserConfigStore
) -> None:
    """``active`` is the *only* movable column: the transaction writes that
    one column and the other eight stay byte for byte."""

    written = planner_constraint(
        target_type=TARGET_TYPE,
        target_id=TARGET_ID,
        scope=PlannerConstraintScope.UNTIL_USER_REENABLES,
        expires_at=None,
        constraint_type=PlannerConstraintType.JUST_CHAT,
    )
    assert isinstance(user_config_store.record_planner_constraint(written), Ok)
    before = _raw(db, CONSTRAINT_ID)
    moved = user_config_store.set_planner_constraint_active(CONSTRAINT_ID, False)
    assert isinstance(moved, Ok)
    after = _raw(db, CONSTRAINT_ID)
    assert after[:8] == before[:8]
    assert after[-1] != before[-1]


@pytest.mark.parametrize("active", [True, False])
def test_transferring_the_current_value_writes_nothing(
    db: sqlite3.Connection,
    user_config_store: SqliteUserConfigStore,
    active: bool,
) -> None:
    written = planner_constraint(active=active)
    assert isinstance(user_config_store.record_planner_constraint(written), Ok)
    before = db.total_changes
    replay = user_config_store.set_planner_constraint_active(CONSTRAINT_ID, active)
    assert isinstance(replay, Ok), replay
    assert replay.value == written
    assert db.total_changes == before


def test_an_unknown_constraint_id_cannot_be_transferred(
    user_config_store: SqliteUserConfigStore,
) -> None:
    refused = user_config_store.set_planner_constraint_active("pc-absent", False)
    assert isinstance(refused, Err), refused
    assert refused.error.code is DomainErrorCode.NOT_FOUND
    assert "pc-absent" in refused.error.message


def test_the_transfer_refuses_a_disabled_then_enabled_round_trip_correctly(
    user_config_store: SqliteUserConfigStore,
) -> None:
    """The ``UNTIL_USER_REENABLES`` lifecycle, end to end: a constraint enters
    enabled, the user clears it, and the user re-enables it — the three reads
    follow the flag at every step."""

    assert isinstance(
        user_config_store.record_planner_constraint(planner_constraint()), Ok
    )
    assert _ids(user_config_store.active_constraints(AS_OF)) == [CONSTRAINT_ID]
    cleared = user_config_store.set_planner_constraint_active(
        CONSTRAINT_ID, False
    )
    assert isinstance(cleared, Ok)
    assert _ids(user_config_store.active_constraints(AS_OF)) == []
    reenabled = user_config_store.set_planner_constraint_active(
        CONSTRAINT_ID, True
    )
    assert isinstance(reenabled, Ok)
    assert _ids(user_config_store.active_constraints(AS_OF)) == [CONSTRAINT_ID]


# -- ④ fencing and read-only-ness --------------------------------------------


def test_a_stale_store_refuses_both_constraint_writes(
    db: sqlite3.Connection, user_config_store: SqliteUserConfigStore
) -> None:
    """The repo-wide epoch fence: a store whose adopted epoch is no longer the
    newest writes nothing and raises (both faces, and the row that the
    transfer would have moved is untouched)."""

    written = planner_constraint()
    assert isinstance(user_config_store.record_planner_constraint(written), Ok)
    from elc.platform.db import epoch

    epoch.open_runtime_epoch(db)
    for write in (
        lambda: user_config_store.record_planner_constraint(
            planner_constraint(OTHER_CONSTRAINT_ID)
        ),
        lambda: user_config_store.set_planner_constraint_active(
            CONSTRAINT_ID, False
        ),
    ):
        try:
            write()
        except StaleStoreEpochError:
            pass
        else:  # pragma: no cover - the assertion is the point
            raise AssertionError("a stale store must refuse the write")
    assert db.execute("SELECT COUNT(*) FROM planner_constraint").fetchone() == (
        1,
    )
    assert _raw(db, CONSTRAINT_ID)[-1] == 1


def test_the_reads_are_read_only(
    db: sqlite3.Connection, user_config_store: SqliteUserConfigStore
) -> None:
    """A read face that wrote would be a projection nobody asked for: the
    connection's own change counter proves none of the three statements
    touched a row."""

    assert isinstance(
        user_config_store.record_planner_constraint(planner_constraint()), Ok
    )
    before = db.total_changes
    user_config_store.get_planner_constraint(CONSTRAINT_ID)
    user_config_store.active_constraints(AS_OF)
    user_config_store.active_constraints_for_target(TARGET_TYPE, TARGET_ID, AS_OF)
    assert db.total_changes == before


# -- ⑤ the identity read -----------------------------------------------------


def test_the_identity_read_answers_none_for_an_unknown_id(
    user_config_store: SqliteUserConfigStore,
) -> None:
    assert user_config_store.get_planner_constraint("pc-absent") == Ok(None)


def test_the_identity_read_has_no_window_judgement(
    user_config_store: SqliteUserConfigStore,
) -> None:
    """A row far outside its window, and a disabled row, both read back
    exactly as written: "in force?" is the active reads' question, not this
    one's."""

    past = planner_constraint(
        starts_at="2020-01-01T00:00:00+00:00",
        expires_at="2020-01-02T00:00:00+00:00",
    )
    assert isinstance(user_config_store.record_planner_constraint(past), Ok)
    disabled = dataclasses.replace(
        planner_constraint(OTHER_CONSTRAINT_ID, active=False)
    )
    assert isinstance(user_config_store.record_planner_constraint(disabled), Ok)
    assert user_config_store.get_planner_constraint(CONSTRAINT_ID) == Ok(past)
    assert user_config_store.get_planner_constraint(
        OTHER_CONSTRAINT_ID
    ) == Ok(disabled)
    assert _ids(user_config_store.active_constraints(AS_OF)) == []


def test_the_identity_read_returns_the_flag_as_a_bool(
    user_config_store: SqliteUserConfigStore,
) -> None:
    assert isinstance(
        user_config_store.record_planner_constraint(planner_constraint()), Ok
    )
    read = user_config_store.get_planner_constraint(CONSTRAINT_ID)
    assert isinstance(read, Ok)
    assert read.value is not None
    assert read.value.active is True


# -- ⑥ the active-window read ------------------------------------------------


def test_no_rows_answers_an_empty_tuple(
    user_config_store: SqliteUserConfigStore,
) -> None:
    assert user_config_store.active_constraints(AS_OF) == Ok(())
    assert user_config_store.active_constraints_for_target(
        TARGET_TYPE, TARGET_ID, AS_OF
    ) == Ok(())


#: (as_of, in_force) triples for the ``starts_at`` boundary: the window opens
#: *at* its start instant, so the instant of the start is already in force.
START_BOUNDARY = (
    ("2026-09-21T09:00:00+00:00", False),
    (CONSTRAINT_START, True),
    ("2026-09-22T09:00:01+00:00", True),
)


@pytest.mark.parametrize("as_of,in_force", START_BOUNDARY)
def test_the_start_boundary_is_inclusive(
    user_config_store: SqliteUserConfigStore, as_of: str, in_force: bool
) -> None:
    assert isinstance(
        user_config_store.record_planner_constraint(planner_constraint()), Ok
    )
    assert bool(_ids(user_config_store.active_constraints(as_of))) is in_force


#: The ``expires_at`` boundary: the window closes *at* its end instant, so the
#: end is still in force and one second later is not.
END_BOUNDARY = (
    ("2026-09-24T09:00:00+00:00", True),
    (CONSTRAINT_END, True),
    ("2026-09-24T09:00:01+00:00", False),
)


@pytest.mark.parametrize("as_of,in_force", END_BOUNDARY)
def test_the_end_boundary_is_inclusive(
    user_config_store: SqliteUserConfigStore, as_of: str, in_force: bool
) -> None:
    assert isinstance(
        user_config_store.record_planner_constraint(planner_constraint()), Ok
    )
    assert bool(_ids(user_config_store.active_constraints(as_of))) is in_force


def test_a_null_expires_at_never_lapses(
    user_config_store: SqliteUserConfigStore,
) -> None:
    """``expires_at IS NULL`` = no end declared (the
    ``UNTIL_USER_REENABLES`` shape): the row is in force arbitrarily late, and
    only the flag or the start can keep it out."""

    open_ended = planner_constraint(
        expires_at=None, scope=PlannerConstraintScope.UNTIL_USER_REENABLES
    )
    assert isinstance(
        user_config_store.record_planner_constraint(open_ended), Ok
    )
    for as_of in (
        CONSTRAINT_START,
        "2036-09-24T09:00:00+00:00",
    ):
        assert _ids(user_config_store.active_constraints(as_of)) == [
            CONSTRAINT_ID
        ]
    assert _ids(user_config_store.active_constraints("2026-09-21T09:00:00+00:00")) == []


def test_an_inactive_row_is_never_in_force(
    user_config_store: SqliteUserConfigStore,
) -> None:
    """A disabled row contains ``as_of`` in its window and is still not in
    force: the flag is the first leg of the reading, not a decoration."""

    assert isinstance(
        user_config_store.record_planner_constraint(
            planner_constraint(active=False)
        ),
        Ok,
    )
    assert _ids(user_config_store.active_constraints(AS_OF)) == []
    assert (
        _ids(
            user_config_store.active_constraints_for_target(
                TARGET_TYPE, TARGET_ID, AS_OF
            )
        )
        == []
    )


def test_a_window_that_ends_before_it_starts_is_never_in_force(
    user_config_store: SqliteUserConfigStore,
) -> None:
    """The two legs are independent comparisons; an inverted window satisfies
    neither, so no instant is inside it."""

    inverted = planner_constraint(
        starts_at="2026-09-24T09:00:00+00:00",
        expires_at="2026-09-22T09:00:00+00:00",
    )
    assert isinstance(user_config_store.record_planner_constraint(inverted), Ok)
    for as_of in (
        "2026-09-21T09:00:00+00:00",
        AS_OF,
        "2026-09-25T09:00:00+00:00",
    ):
        assert _ids(user_config_store.active_constraints(as_of)) == []


def test_the_answer_is_ordered_by_constraint_id(
    user_config_store: SqliteUserConfigStore,
) -> None:
    """Deterministic order, declared: ``constraint_id`` ascending. The rows
    are written out of order so the answer cannot be insertion order."""

    for constraint_id in ("pc-c", "pc-a", "pc-b"):
        assert isinstance(
            user_config_store.record_planner_constraint(
                planner_constraint(constraint_id)
            ),
            Ok,
        )
    assert _ids(user_config_store.active_constraints(AS_OF)) == [
        "pc-a",
        "pc-b",
        "pc-c",
    ]


def test_the_order_does_not_depend_on_the_window(
    user_config_store: SqliteUserConfigStore,
) -> None:
    """Two rows in force at the same instant, with different starts: the order
    is the id, not the window (a stable answer for a consumer that diffs
    two reads)."""

    later = planner_constraint(
        "pc-later",
        starts_at="2026-09-23T00:00:00+00:00",
        expires_at="2026-09-24T09:00:00+00:00",
    )
    earlier = planner_constraint(
        "pc-earlier",
        starts_at=CONSTRAINT_START,
        expires_at="2026-09-30T09:00:00+00:00",
    )
    assert isinstance(user_config_store.record_planner_constraint(later), Ok)
    assert isinstance(user_config_store.record_planner_constraint(earlier), Ok)
    assert _ids(user_config_store.active_constraints(AS_OF)) == [
        "pc-earlier",
        "pc-later",
    ]


def test_the_start_leg_compares_instants_not_text(
    user_config_store: SqliteUserConfigStore,
) -> None:
    """The comparison is temporal, not textual — and the two readings really
    differ here, so this test is load-bearing rather than accidentally right.

    The window opens at ``2026-09-23T17:00:00+08:00``, which is exactly
    ``as_of`` (09:00Z) — the inclusive boundary, so the row is in force. A
    **byte** comparison would put the ``+08:00`` spelling *after* the
    ``+00:00`` one and answer "not started yet", the opposite verdict.
    """

    tokyo_open = planner_constraint(
        starts_at="2026-09-23T17:00:00+08:00",
        expires_at=None,
    )
    assert tokyo_open.starts_at > AS_OF  # the byte order, for the record
    assert isinstance(user_config_store.record_planner_constraint(tokyo_open), Ok)
    assert _ids(user_config_store.active_constraints(AS_OF)) == [CONSTRAINT_ID]


def test_the_end_leg_compares_instants_not_text(
    user_config_store: SqliteUserConfigStore,
) -> None:
    """The other half, with a window whose end is *earlier* than ``as_of`` as
    an instant while its text sorts *later*: 10:30+09:00 is 01:30Z, before the
    09:00Z question, so the row has lapsed — and a byte comparison would keep
    it in force."""

    tokyo_close = planner_constraint(
        starts_at="2026-09-22T09:00:00+00:00",
        expires_at="2026-09-23T10:30:00+09:00",
    )
    assert tokyo_close.expires_at is not None
    assert tokyo_close.expires_at > AS_OF  # the byte order, for the record
    assert isinstance(
        user_config_store.record_planner_constraint(tokyo_close), Ok
    )
    assert _ids(user_config_store.active_constraints(AS_OF)) == []


def test_a_window_written_in_another_offset_answers_the_same_instants(
    user_config_store: SqliteUserConfigStore,
) -> None:
    """Two spellings of one window — one in ``+00:00``, one in ``+08:00`` —
    answer identically at every boundary instant: the offset is a spelling,
    the instant is the fact."""

    in_utc = planner_constraint(
        "pc-utc",
        starts_at=CONSTRAINT_START,
        expires_at=CONSTRAINT_END,
    )
    in_tokyo = planner_constraint(
        "pc-tokyo",
        starts_at="2026-09-22T17:00:00+08:00",
        expires_at="2026-09-24T17:00:00+08:00",
    )
    assert isinstance(user_config_store.record_planner_constraint(in_utc), Ok)
    assert isinstance(user_config_store.record_planner_constraint(in_tokyo), Ok)
    for as_of in (CONSTRAINT_START, AS_OF, CONSTRAINT_END):
        assert _ids(user_config_store.active_constraints(as_of)) == [
            "pc-tokyo",
            "pc-utc",
        ], as_of
    for as_of in (
        "2026-09-22T08:59:59+00:00",
        "2026-09-24T09:00:01+00:00",
    ):
        assert _ids(user_config_store.active_constraints(as_of)) == [], as_of


def test_the_read_answers_about_the_instant_it_is_given(
    user_config_store: SqliteUserConfigStore,
) -> None:
    """Two calls with different instants answer differently, and the same
    instant always answers the same way (no clock is consulted)."""

    assert isinstance(
        user_config_store.record_planner_constraint(planner_constraint()), Ok
    )
    assert _ids(user_config_store.active_constraints(AS_OF)) == [CONSTRAINT_ID]
    outside = "2026-09-25T09:00:00+00:00"
    assert _ids(user_config_store.active_constraints(outside)) == []
    assert _ids(user_config_store.active_constraints(AS_OF)) == [CONSTRAINT_ID]


def test_a_naive_window_is_refused_when_the_read_must_compare_it(
    user_config_store: SqliteUserConfigStore,
) -> None:
    """A durable row with no offset cannot be placed on a timeline: the read
    says so instead of assuming a zone."""

    assert isinstance(
        user_config_store.record_planner_constraint(
            planner_constraint(starts_at="2026-09-22T09:00:00")
        ),
        Ok,
    )
    refused = user_config_store.active_constraints(AS_OF)
    assert isinstance(refused, Err), refused
    assert refused.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "starts_at" in refused.error.message
    assert CONSTRAINT_ID in refused.error.message


def test_an_unreadable_expires_at_is_refused_when_it_must_be_compared(
    user_config_store: SqliteUserConfigStore,
) -> None:
    assert isinstance(
        user_config_store.record_planner_constraint(
            planner_constraint(expires_at="whenever")
        ),
        Ok,
    )
    refused = user_config_store.active_constraints(AS_OF)
    assert isinstance(refused, Err), refused
    assert refused.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "expires_at" in refused.error.message


def test_a_disabled_row_with_an_unreadable_window_breaks_no_read(
    user_config_store: SqliteUserConfigStore,
) -> None:
    """The flag is decided by the statement, so a row already filtered out is
    never parsed: a disabled row's junk timestamps cannot take the read down
    with them."""

    assert isinstance(
        user_config_store.record_planner_constraint(
            planner_constraint(
                "pc-junk",
                active=False,
                starts_at="not-a-time",
                expires_at="also-not",
            )
        ),
        Ok,
    )
    assert isinstance(
        user_config_store.record_planner_constraint(planner_constraint()), Ok
    )
    assert _ids(user_config_store.active_constraints(AS_OF)) == [CONSTRAINT_ID]


#: The three unusable ``as_of`` values a caller can hand in.
BAD_AS_OF = ("", "yesterday", "2026-09-23T09:00:00")


@pytest.mark.parametrize("as_of", BAD_AS_OF)
def test_an_unusable_as_of_is_refused(
    user_config_store: SqliteUserConfigStore, as_of: str
) -> None:
    assert isinstance(
        user_config_store.record_planner_constraint(planner_constraint()), Ok
    )
    refused = user_config_store.active_constraints(as_of)
    assert isinstance(refused, Err), refused
    assert refused.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "as_of" in refused.error.message


@pytest.mark.parametrize("as_of", BAD_AS_OF)
def test_the_refusal_carries_no_bare_exception_text(
    user_config_store: SqliteUserConfigStore, as_of: str
) -> None:
    """The message is this domain's words: no exception class name, no
    traceback, no sqlite vocabulary."""

    refused = user_config_store.active_constraints(as_of)
    assert isinstance(refused, Err)
    lowered = refused.error.message.lower()
    for leak in ("valueerror", "traceback", "sqlite", "exception"):
        assert leak not in lowered, leak


@pytest.mark.parametrize("as_of", BAD_AS_OF)
def test_the_target_read_refuses_the_same_as_of(
    user_config_store: SqliteUserConfigStore, as_of: str
) -> None:
    refused = user_config_store.active_constraints_for_target(
        TARGET_TYPE, TARGET_ID, as_of
    )
    assert isinstance(refused, Err), refused
    assert refused.error.code is DomainErrorCode.VALIDATION_FAILED


# -- ⑦ the target leg --------------------------------------------------------


def test_a_null_target_leg_is_not_target_limited(
    user_config_store: SqliteUserConfigStore,
) -> None:
    """A constraint about teaching in general applies to every target — that
    is what the NULL pair means (§9's two ``?`` columns)."""

    general = planner_constraint("pc-general")
    assert isinstance(user_config_store.record_planner_constraint(general), Ok)
    for target_type, target_id in (
        (TARGET_TYPE, TARGET_ID),
        ("CAPABILITY", TargetId("cap-ref-ask-clarification")),
    ):
        assert _ids(
            user_config_store.active_constraints_for_target(
                target_type, target_id, AS_OF
            )
        ) == ["pc-general"]


def test_a_matching_target_pair_is_returned(
    user_config_store: SqliteUserConfigStore,
) -> None:
    specific = planner_constraint(
        "pc-specific", target_type=TARGET_TYPE, target_id=TARGET_ID
    )
    assert isinstance(user_config_store.record_planner_constraint(specific), Ok)
    assert _ids(
        user_config_store.active_constraints_for_target(
            TARGET_TYPE, TARGET_ID, AS_OF
        )
    ) == ["pc-specific"]


def test_a_differing_target_id_is_not_returned(
    user_config_store: SqliteUserConfigStore,
) -> None:
    specific = planner_constraint(
        "pc-specific", target_type=TARGET_TYPE, target_id=TARGET_ID
    )
    assert isinstance(user_config_store.record_planner_constraint(specific), Ok)
    assert (
        _ids(
            user_config_store.active_constraints_for_target(
                TARGET_TYPE, TargetId("res-other"), AS_OF
            )
        )
        == []
    )


def test_a_differing_target_type_is_not_returned(
    user_config_store: SqliteUserConfigStore,
) -> None:
    """The target vocabulary is part of the key: the same id under the other
    type is a different target."""

    specific = planner_constraint(
        "pc-specific", target_type=TARGET_TYPE, target_id=TARGET_ID
    )
    assert isinstance(user_config_store.record_planner_constraint(specific), Ok)
    assert (
        _ids(
            user_config_store.active_constraints_for_target(
                "CAPABILITY", TARGET_ID, AS_OF
            )
        )
        == []
    )


def test_a_half_declared_target_leg_matches_no_target(
    user_config_store: SqliteUserConfigStore,
) -> None:
    """§9 pins no rule relating the two target columns, so this cut invents
    none — but a row with one leg and not the other is neither
    target-limited (it does not have the NULL pair) nor about this target (its
    pair is not verbatim), so it is in no target-scoped answer. It stays
    readable through the identity read.

    **Both** half shapes are pinned, and each one discriminates on its own: a
    reading that treated "``target_type`` is NULL" as "not target-limited"
    would match the second row (type NULL, id present) against every target,
    while a reading that treated "``target_id`` is NULL" as general would
    match the first.
    """

    type_without_id = planner_constraint("pc-half-type", target_type=TARGET_TYPE)
    id_without_type = planner_constraint("pc-half-id", target_id=TARGET_ID)
    for half in (type_without_id, id_without_type):
        assert isinstance(user_config_store.record_planner_constraint(half), Ok)
        assert (
            _ids(
                user_config_store.active_constraints_for_target(
                    TARGET_TYPE, TARGET_ID, AS_OF
                )
            )
            == []
        )
        assert user_config_store.get_planner_constraint(
            half.constraint_id
        ) == Ok(half)
    # The general read is not target-scoped, so it still sees both rows.
    assert _ids(user_config_store.active_constraints(AS_OF)) == [
        "pc-half-id",
        "pc-half-type",
    ]


def test_the_target_read_applies_the_window_leg_too(
    user_config_store: SqliteUserConfigStore,
) -> None:
    general = planner_constraint("pc-general")
    assert isinstance(user_config_store.record_planner_constraint(general), Ok)
    assert _ids(
        user_config_store.active_constraints_for_target(
            TARGET_TYPE, TARGET_ID, AS_OF
        )
    ) == ["pc-general"]
    assert (
        _ids(
            user_config_store.active_constraints_for_target(
                TARGET_TYPE, TARGET_ID, "2026-09-25T09:00:00+00:00"
            )
        )
        == []
    )


def test_the_target_read_orders_like_the_general_one(
    user_config_store: SqliteUserConfigStore,
) -> None:
    for constraint_id in ("pc-c", "pc-a", "pc-b"):
        assert isinstance(
            user_config_store.record_planner_constraint(
                planner_constraint(constraint_id)
            ),
            Ok,
        )
    assert _ids(
        user_config_store.active_constraints_for_target(
            TARGET_TYPE, TARGET_ID, AS_OF
        )
    ) == ["pc-a", "pc-b", "pc-c"]


def test_the_two_active_reads_agree_on_the_general_set(
    user_config_store: SqliteUserConfigStore,
) -> None:
    """The target read is the general read narrowed — never a different
    window reading: everything the general read answers for a target that no
    row names is answered here too."""

    for constraint_id in ("pc-a", "pc-b"):
        assert isinstance(
            user_config_store.record_planner_constraint(
                planner_constraint(constraint_id, target_type=TARGET_TYPE)
            ),
            Ok,
        )
    general = user_config_store.active_constraints(AS_OF)
    assert isinstance(general, Ok)
    assert len(general.value) == 2
    assert (
        _ids(
            user_config_store.active_constraints_for_target(
                TARGET_TYPE, TargetId("res-other"), AS_OF
            )
        )
        == []
    )


def test_a_target_limited_row_is_in_the_general_answer_too(
    user_config_store: SqliteUserConfigStore,
) -> None:
    """``active_constraints`` asks no target question, so a target-limited row
    is in force by the window and answers here; the target read is where the
    narrowing happens."""

    specific = planner_constraint(
        "pc-specific", target_type=TARGET_TYPE, target_id=TARGET_ID
    )
    assert isinstance(user_config_store.record_planner_constraint(specific), Ok)
    assert _ids(user_config_store.active_constraints(AS_OF)) == ["pc-specific"]
