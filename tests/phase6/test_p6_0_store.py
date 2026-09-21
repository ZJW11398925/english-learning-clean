"""P6-0 ③ — the durable rows: write semantics, read-back, and the refuse
paths.

docs/DATA_MODEL.md §1.4 ("version every derived model") and §1.3
(append-first) are the two rules this file makes observable:

- a new object inserts; the same version with the same content is an
  idempotent replay that writes nothing; a moved version replaces; and the
  same version with *different* content is refused with **zero writes** —
  configuration is never silently rewritten;
- ``SessionFocus`` has no version column in §5.1 at all, so its identity is
  one-shot: the same id is a replay when the content is equal and a refusal
  when it is not (a new focus is a new id — append-first), and several
  focuses for one conversation coexist.

Every assertion reads the durable row back (or the raw column), never the
caller's construction: the store's contract is that what it returns is what a
later read returns.
"""

from __future__ import annotations

import dataclasses
import json
import sqlite3

from elc.platform.db import epoch
from elc.platform.types import GoalModality, Ok
from elc.user_config.store import SqliteUserConfigStore, StaleStoreEpochError
from elc.user_config.types import (
    LearningGoalPortfolio,
    SessionFocus,
    TeachingFrequency,
    TeachingPolicyProfile,
)
from tests.conftest import SRC_ROOT
from tests.phase3.sql_write_scan import write_targets

from .conftest import (
    OTHER_USER,
    USER,
    goal,
    portfolio,
    session_focus,
    teaching_policy,
)

_UNPINNED_RAW = {
    "mode": "PREVIEW_V0",
    "interruption_budget": "three-per-session",
    "curriculum_initiative": "ask-first",
    "correction_strictness": "gentle",
    "hint_policy": "ladder",
    "assessment_visibility": "own-only",
    "practice_density": "sparse",
    "persona_freedom": "full",
}


def _portfolio_row(db: sqlite3.Connection) -> tuple[object, ...]:
    row = db.execute(
        "SELECT goal_portfolio_id, goal_version, goals, modality_weights,"
        " assessment_targets, register_style_goals, effective_from,"
        " updated_at FROM goal_portfolio"
    ).fetchone()
    assert row is not None, "no goal_portfolio row"
    return tuple(row)


def _policy_row(db: sqlite3.Connection) -> tuple[object, ...]:
    row = db.execute(
        "SELECT teaching_policy_profile_id, policy_version, mode,"
        " teaching_frequency, interruption_budget, curriculum_initiative,"
        " correction_strictness, hint_policy, assessment_visibility,"
        " practice_density, persona_freedom, effective_from, updated_at"
        " FROM teaching_policy"
    ).fetchone()
    assert row is not None, "no teaching_policy row"
    return tuple(row)


def _focus_row(db: sqlite3.Connection, focus_id: str) -> tuple[object, ...]:
    row = db.execute(
        "SELECT session_focus_id, conversation_id,"
        " base_goal_portfolio_version, temporary_goal_weights,"
        " manual_focus_target, starts_at, expires_at FROM session_focus"
        " WHERE session_focus_id = ?",
        (focus_id,),
    ).fetchone()
    assert row is not None, f"no session_focus row {focus_id}"
    return tuple(row)


def _field_pairs(durable, written) -> list[tuple[str, object, object]]:
    """Every field of a written object next to the read-back one."""

    return [
        (field.name, getattr(written, field.name), getattr(durable, field.name))
        for field in dataclasses.fields(durable)
    ]


# -- the portfolio ----------------------------------------------------------


def test_a_new_portfolio_inserts_and_reads_back_field_for_field(
    db: sqlite3.Connection, user_config_store: SqliteUserConfigStore
) -> None:
    written = user_config_store.upsert_goal_portfolio(
        portfolio(
            goal("g-speaking", modality=GoalModality.SPEAKING),
            goal("g-reading", modality=GoalModality.READING),
        )
    )
    assert isinstance(written, Ok), written
    read = user_config_store.get_goal_portfolio(USER)
    assert isinstance(read, Ok) and read.value is not None
    assert _field_pairs(read.value, written.value) == [
        (field.name, getattr(written.value, field.name),
         getattr(written.value, field.name))
        for field in dataclasses.fields(LearningGoalPortfolio)
    ]
    assert read.value == written.value

    row = _portfolio_row(db)
    assert row[0] == str(USER)
    assert row[1] == "gv-1"
    assert json.loads(str(row[2])) == [
        {
            "goal_id": "g-speaking",
            "goal_modality": "SPEAKING",
            "description": "a long-term goal",
        },
        {
            "goal_id": "g-reading",
            "goal_modality": "READING",
            "description": "a long-term goal",
        },
    ]
    assert json.loads(str(row[3])) == {"SPEAKING": 0.6, "LISTENING": 0.4}
    assert json.loads(str(row[4])) == ["ielts-speaking"]
    assert json.loads(str(row[5])) == ["workplace-formal"]
    assert row[6] == "2026-09-22T00:00:00+00:00"
    assert row[7] == written.value.updated_at


def test_an_unchanged_portfolio_replays_idempotently(
    db: sqlite3.Connection, user_config_store: SqliteUserConfigStore
) -> None:
    first = user_config_store.upsert_goal_portfolio(portfolio(goal("g-1")))
    assert isinstance(first, Ok), first
    before = _portfolio_row(db)
    again = user_config_store.upsert_goal_portfolio(portfolio(goal("g-1")))
    assert isinstance(again, Ok), again
    assert again.value == first.value
    assert _portfolio_row(db) == before  # zero writes, same stamp


def test_a_moved_version_replaces_the_portfolio(
    db: sqlite3.Connection, user_config_store: SqliteUserConfigStore
) -> None:
    assert isinstance(
        user_config_store.upsert_goal_portfolio(portfolio(goal("g-1"))), Ok
    )
    moved = user_config_store.upsert_goal_portfolio(
        portfolio(goal("g-2"), version="gv-2")
    )
    assert isinstance(moved, Ok), moved
    row = _portfolio_row(db)
    assert row[1] == "gv-2"
    assert json.loads(str(row[2]))[0]["goal_id"] == "g-2"
    assert row[7] == moved.value.updated_at
    read = user_config_store.get_goal_portfolio(USER)
    assert isinstance(read, Ok) and read.value == moved.value


def test_the_same_version_with_different_content_is_refused(
    db: sqlite3.Connection, user_config_store: SqliteUserConfigStore
) -> None:
    assert isinstance(
        user_config_store.upsert_goal_portfolio(portfolio(goal("g-1"))), Ok
    )
    before = _portfolio_row(db)
    refused = user_config_store.upsert_goal_portfolio(portfolio(goal("g-2")))
    assert not isinstance(refused, Ok)
    assert refused.error.code.value == "CONFLICT"
    assert "goal_version" in refused.error.message
    assert _portfolio_row(db) == before  # zero writes


def test_the_weight_map_order_is_not_content_but_an_extra_pair_is(
    db: sqlite3.Connection, user_config_store: SqliteUserConfigStore
) -> None:
    weights = {GoalModality.SPEAKING: 0.6, GoalModality.LISTENING: 0.4}
    first = user_config_store.upsert_goal_portfolio(
        portfolio(goal("g-1"), weights=weights)
    )
    assert isinstance(first, Ok), first
    before = _portfolio_row(db)
    reordered = user_config_store.upsert_goal_portfolio(
        portfolio(
            goal("g-1"),
            weights={
                GoalModality.LISTENING: 0.4,
                GoalModality.SPEAKING: 0.6,
            },
        )
    )
    assert isinstance(reordered, Ok), reordered
    assert _portfolio_row(db) == before

    with_zero = user_config_store.upsert_goal_portfolio(
        portfolio(goal("g-1"), weights={**weights, GoalModality.WRITING: 0.0})
    )
    assert not isinstance(with_zero, Ok)
    assert with_zero.error.code.value == "CONFLICT"
    assert _portfolio_row(db) == before


def test_the_goal_list_order_is_content(
    db: sqlite3.Connection, user_config_store: SqliteUserConfigStore
) -> None:
    assert isinstance(
        user_config_store.upsert_goal_portfolio(
            portfolio(goal("g-1"), goal("g-2"))
        ),
        Ok,
    )
    before = _portfolio_row(db)
    reordered = user_config_store.upsert_goal_portfolio(
        portfolio(goal("g-2"), goal("g-1"))
    )
    assert not isinstance(reordered, Ok)
    assert reordered.error.code.value == "CONFLICT"
    assert _portfolio_row(db) == before


def test_effective_from_is_the_callers_and_is_never_invented(
    db: sqlite3.Connection, user_config_store: SqliteUserConfigStore
) -> None:
    silent = user_config_store.upsert_goal_portfolio(
        portfolio(goal("g-1"), effective_from="")
    )
    assert isinstance(silent, Ok), silent
    assert _portfolio_row(db)[6] == ""
    assert silent.value.effective_from == ""

    declared = user_config_store.upsert_goal_portfolio(
        portfolio(
            goal("g-1"),
            version="gv-2",
            effective_from="2026-10-01T00:00:00+00:00",
        )
    )
    assert isinstance(declared, Ok), declared
    assert _portfolio_row(db)[6] == "2026-10-01T00:00:00+00:00"


# -- the teaching policy ----------------------------------------------------


def test_a_new_policy_inserts_and_reads_back_field_for_field(
    db: sqlite3.Connection, user_config_store: SqliteUserConfigStore
) -> None:
    written = user_config_store.upsert_teaching_policy(teaching_policy())
    assert isinstance(written, Ok), written
    read = user_config_store.get_teaching_policy(USER)
    assert isinstance(read, Ok) and read.value is not None
    assert read.value == written.value
    assert _field_pairs(read.value, written.value) == [
        (field.name, getattr(written.value, field.name),
         getattr(written.value, field.name))
        for field in dataclasses.fields(TeachingPolicyProfile)
    ]
    # "Not configured" is a value the row carries: the eight unpinned
    # columns are NULL and read back as None.
    row = _policy_row(db)
    assert row[2] == row[4] == row[5] == row[6] == row[7] == row[8] == row[9]
    assert row[2] is None and row[10] is None
    assert row[3] == "BALANCED"


def test_the_unpinned_columns_carry_raw_values_verbatim(
    db: sqlite3.Connection, user_config_store: SqliteUserConfigStore
) -> None:
    """No interpretation anywhere: a value this slice has no vocabulary for
    survives the round trip unchanged (it is not rejected, normalized, or
    resolved into a word list)."""

    written = user_config_store.upsert_teaching_policy(
        teaching_policy(**_UNPINNED_RAW)
    )
    assert isinstance(written, Ok), written
    read = user_config_store.get_teaching_policy(USER)
    assert isinstance(read, Ok) and read.value is not None
    for column, value in _UNPINNED_RAW.items():
        assert getattr(read.value, column) == value, column
    row = _policy_row(db)
    assert row[2] == "PREVIEW_V0"
    assert row[10] == "full"


def test_an_unchanged_policy_replays_idempotently(
    db: sqlite3.Connection, user_config_store: SqliteUserConfigStore
) -> None:
    first = user_config_store.upsert_teaching_policy(teaching_policy())
    assert isinstance(first, Ok), first
    before = _policy_row(db)
    again = user_config_store.upsert_teaching_policy(teaching_policy())
    assert isinstance(again, Ok), again
    assert again.value == first.value
    assert _policy_row(db) == before


def test_a_moved_version_replaces_the_policy(
    db: sqlite3.Connection, user_config_store: SqliteUserConfigStore
) -> None:
    assert isinstance(
        user_config_store.upsert_teaching_policy(teaching_policy()), Ok
    )
    moved = user_config_store.upsert_teaching_policy(
        teaching_policy(version="pv-2", frequency=TeachingFrequency.MINIMAL)
    )
    assert isinstance(moved, Ok), moved
    row = _policy_row(db)
    assert row[1] == "pv-2"
    assert row[3] == "MINIMAL"


def test_none_is_a_value_not_a_wildcard(
    db: sqlite3.Connection, user_config_store: SqliteUserConfigStore
) -> None:
    """The same version with one previously-unset column set is different
    content — the store cannot know that None "meant the same"."""

    assert isinstance(
        user_config_store.upsert_teaching_policy(teaching_policy()), Ok
    )
    before = _policy_row(db)
    refused = user_config_store.upsert_teaching_policy(
        teaching_policy(mode="SOCRATIC")
    )
    assert not isinstance(refused, Ok)
    assert refused.error.code.value == "CONFLICT"
    assert _policy_row(db) == before


def test_every_declared_frequency_word_round_trips(
    db: sqlite3.Connection, user_config_store: SqliteUserConfigStore
) -> None:
    for index, word in enumerate(TeachingFrequency, start=1):
        written = user_config_store.upsert_teaching_policy(
            teaching_policy(version=f"pv-{index}", frequency=word)
        )
        assert isinstance(written, Ok), written
        read = user_config_store.get_teaching_policy(USER)
        assert isinstance(read, Ok) and read.value is not None
        assert read.value.teaching_frequency is word


# -- the session focus ------------------------------------------------------


def test_a_new_focus_inserts_and_reads_back_field_for_field(
    db: sqlite3.Connection,
    user_config_store: SqliteUserConfigStore,
    conversation,
) -> None:
    del conversation
    written = user_config_store.set_session_focus(
        session_focus(
            "sf-with-target",
            target="res-hedge-i-think",
            expires_at="2026-09-22T11:00:00+00:00",
        )
    )
    assert isinstance(written, Ok), written
    read = user_config_store.get_session_focus("sf-with-target")
    assert isinstance(read, Ok) and read.value is not None
    assert read.value == written.value
    assert _field_pairs(read.value, written.value) == [
        (field.name, getattr(written.value, field.name),
         getattr(written.value, field.name))
        for field in dataclasses.fields(SessionFocus)
    ]

    open_ended = user_config_store.set_session_focus(session_focus("sf-open"))
    assert isinstance(open_ended, Ok), open_ended
    assert open_ended.value.manual_focus_target is None
    assert open_ended.value.expires_at is None
    row = _focus_row(db, "sf-open")
    assert row[4] is None and row[6] is None
    assert row[3] == json.dumps({"SPEAKING": 1.0}, sort_keys=True,
                                separators=(",", ":"))


def test_an_unchanged_focus_replays_idempotently(
    db: sqlite3.Connection,
    user_config_store: SqliteUserConfigStore,
    conversation,
) -> None:
    del conversation
    first = user_config_store.set_session_focus(session_focus("sf-1"))
    assert isinstance(first, Ok), first
    before = _focus_row(db, "sf-1")
    again = user_config_store.set_session_focus(session_focus("sf-1"))
    assert isinstance(again, Ok), again
    assert again.value == first.value
    assert _focus_row(db, "sf-1") == before


def test_a_focus_identity_is_one_shot(
    db: sqlite3.Connection,
    user_config_store: SqliteUserConfigStore,
    conversation,
) -> None:
    """§5.1 pins no version column for SessionFocus, so there is nothing to
    rewrite the row under: different content under the same id is refused
    (append-first — a new focus is a new id), with zero writes."""

    del conversation
    assert isinstance(
        user_config_store.set_session_focus(session_focus("sf-1")), Ok
    )
    before = _focus_row(db, "sf-1")
    refused = user_config_store.set_session_focus(
        session_focus("sf-1", weights={GoalModality.READING: 1.0})
    )
    assert not isinstance(refused, Ok)
    assert refused.error.code.value == "CONFLICT"
    assert "session_focus_id" in refused.error.message
    assert _focus_row(db, "sf-1") == before

    # The escape hatch the message names: a new id.
    fresh = user_config_store.set_session_focus(
        session_focus("sf-2", weights={GoalModality.READING: 1.0})
    )
    assert isinstance(fresh, Ok), fresh
    assert user_config_store.get_session_focus("sf-2").value == fresh.value


def test_several_focuses_for_one_conversation_coexist(
    db: sqlite3.Connection,
    user_config_store: SqliteUserConfigStore,
    conversation,
) -> None:
    del conversation
    for index in (1, 2, 3):
        written = user_config_store.set_session_focus(
            session_focus(f"sf-{index}", starts_at=f"2026-09-2{index}T09:00:00+00:00")
        )
        assert isinstance(written, Ok), written
    rows = db.execute(
        "SELECT session_focus_id FROM session_focus ORDER BY session_focus_id"
    ).fetchall()
    assert [str(row[0]) for row in rows] == ["sf-1", "sf-2", "sf-3"]


def test_a_focus_for_an_unknown_conversation_is_refused(
    db: sqlite3.Connection, user_config_store: SqliteUserConfigStore
) -> None:
    from elc.platform.types import ConversationId as ConvId

    refused = user_config_store.set_session_focus(
        session_focus("sf-ghost", conversation=ConvId("conv-not-open"))
    )
    assert not isinstance(refused, Ok)
    assert refused.error.code.value == "CONFLICT"
    assert db.execute("SELECT COUNT(*) FROM session_focus").fetchone() == (0,)


# -- reads, fencing and the module's own reach ------------------------------


def test_the_p6_0_reads_do_not_need_a_write_to_answer(
    user_config_store: SqliteUserConfigStore,
) -> None:
    """A never-written world answers ``Ok(None)`` — the fail-closed read the
    controller's disclosure face already ships, kept for the new objects
    (and keyed by the object's own key: an unknown user is not a focus)."""

    for read in (
        user_config_store.get_goal_portfolio(OTHER_USER),
        user_config_store.get_teaching_policy(OTHER_USER),
        user_config_store.get_session_focus("sf-absent"),
        user_config_store.get_session_focus(str(USER)),
    ):
        assert isinstance(read, Ok) and read.value is None


def test_a_stale_store_refuses_every_p6_0_write(
    db: sqlite3.Connection, user_config_store: SqliteUserConfigStore
) -> None:
    """The epoch fence is the repo-wide one: a store whose adopted epoch is
    no longer the newest writes nothing and raises."""

    epoch.open_runtime_epoch(db)
    for write in (
        lambda: user_config_store.upsert_goal_portfolio(portfolio(goal("g-1"))),
        lambda: user_config_store.upsert_teaching_policy(teaching_policy()),
        lambda: user_config_store.set_session_focus(session_focus("sf-1")),
    ):
        try:
            write()
        except StaleStoreEpochError:
            pass
        else:  # pragma: no cover - the assertion is the point
            raise AssertionError("a stale store must refuse the write")
    for table in ("goal_portfolio", "teaching_policy", "session_focus"):
        assert db.execute(f"SELECT COUNT(*) FROM {table}").fetchone() == (0,)


def test_the_store_writes_the_five_configuration_tables_and_nothing_else() -> None:
    """The durable face of this context cannot reach learning truth: an AST
    scan over the store's own statement literals finds exactly the five
    configuration tables (invariant ③'s structural half)."""

    targets = write_targets(SRC_ROOT / "user_config" / "store.py")
    assert targets == {
        "user_profile",
        "disclosure_policy",
        "goal_portfolio",
        "teaching_policy",
        "session_focus",
    }
    assert not {
        name
        for name in targets
        if name.startswith(("evidence", "learner", "learning"))
    }


def test_the_durable_writes_leave_no_shadow_rows(
    db: sqlite3.Connection, user_config_store: SqliteUserConfigStore
) -> None:
    """One row per object, written once and replaced in place: the append
    convention belongs to *facts* (§1.3), not to a versioned configuration
    row — the durable table is the current state, and the old version is
    gone by design (the stamp is the history)."""

    conversation_id = "conv-p6-0"
    db.execute(
        "INSERT INTO conversation (conversation_id, persona_id, scene_id,"
        " created_at, status, next_turn_sequence, next_message_sequence)"
        " VALUES (?, NULL, NULL, 'now', 'ACTIVE', 1, 1)",
        (conversation_id,),
    )
    db.commit()
    assert isinstance(
        user_config_store.upsert_goal_portfolio(portfolio(goal("g-1"))), Ok
    )
    assert isinstance(
        user_config_store.upsert_goal_portfolio(
            portfolio(goal("g-2"), version="gv-2")
        ),
        Ok,
    )
    assert isinstance(
        user_config_store.upsert_teaching_policy(teaching_policy()), Ok
    )
    assert isinstance(
        user_config_store.upsert_teaching_policy(
            teaching_policy(version="pv-2")
        ),
        Ok,
    )
    assert isinstance(
        user_config_store.set_session_focus(session_focus("sf-1")), Ok
    )
    for table in ("goal_portfolio", "teaching_policy", "session_focus"):
        assert db.execute(f"SELECT COUNT(*) FROM {table}").fetchone() == (1,)
