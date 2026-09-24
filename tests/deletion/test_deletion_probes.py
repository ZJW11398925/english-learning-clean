"""Gate 2 — the real-app.db probes.

Every row this module asserts on is produced by the shipped chain: migrations
→ the runtime epoch → the ConversationCoordinator (real turns, real silent
evidence) → the CP4 projection runtime → the domain stores' own write faces.
There is no ``_seed``-style helper and no fixture module supplying rows, which
is the same red line the Phase 5/6 suites hold.

Each scope is probed **twice**: once for what it must remove, once for what it
must leave alone. The counter-example half is the one that matters most — a
deletion that removes too much is the failure SEC-026/SEC-027 exist to
prevent, and a probe that only checks "the thing is gone" cannot see it.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from elc.deletion.types import (
    SCOPE_SWEPT_TABLES,
    DeletionRequest,
    DeletionScope,
)
from elc.platform.types import GoalModality, GoalVersion, Ok, PolicyVersion
from elc.user_config.types import (
    DisclosureLevel,
    DisclosurePolicy,
    DisclosureRule,
    LearningGoalPortfolio,
    SessionFocus,
    TeachingFrequency,
    TeachingPolicyProfile,
)
from tests.deletion.conftest import (
    CONV,
    CONV_OTHER,
    CONV_OTHER_PERSONA,
    MAIN_MEMORY,
    PERSONA,
    PERSONA_OTHER,
    TARGET_ID,
    USER,
    World,
    _digest,
)


def _count(db: sqlite3.Connection, table: str, where: str = "", params=()) -> int:
    sql = f"SELECT COUNT(*) FROM {table}"
    if where:
        sql = sql + " WHERE " + where
    row = db.execute(sql, params).fetchone()
    return 0 if row is None else int(row[0])


# ---------------------------------------------------------------------------
# The world is real: the chain produced the rows the probes need
# ---------------------------------------------------------------------------


def test_the_world_carries_real_evidence(
    db: sqlite3.Connection, world: World
) -> None:
    """The silent chain landed real learning rows (not a fixture)."""

    assert _count(db, "evidence_claim") >= 1
    assert _count(db, "evidence_group") >= 1
    assert _count(db, "turn_record") == 3
    assert _count(db, "episode") == 3
    assert _count(db, "relationship_memory") == 3


def test_the_world_carries_a_committed_episode_job(
    db: sqlite3.Connection, world: World
) -> None:
    rows = db.execute(
        "SELECT DISTINCT status FROM projection_job"
    ).fetchall()
    assert [str(row[0]) for row in rows] == ["COMMITTED"]


# ---------------------------------------------------------------------------
# §19 CONVERSATION — positive and counter-example
# ---------------------------------------------------------------------------


def test_conversation_deletion_removes_the_conversations_own_chain(
    db: sqlite3.Connection, world: World, deletion_controller
) -> None:
    result = deletion_controller.execute(
        DeletionRequest(
            scope=DeletionScope.CONVERSATION, conversation_id=CONV
        )
    )
    assert isinstance(result, Ok), result
    execution = result.value.execution

    assert _count(
        db, "conversation", "conversation_id = ?", (str(CONV),)
    ) == 0
    assert _count(db, "turn_record", "conversation_id = ?", (str(CONV),)) == 0
    assert _count(db, "user_turn", "conversation_id = ?", (str(CONV),)) == 0
    assert _count(db, "input_envelope", "conversation_id = ?", (str(CONV),)) == 0
    assert _count(db, "episode", "conversation_id = ?", (str(CONV),)) == 0
    # The turn's provenance legs are gone with it.
    assert _count(
        db, "projection_job", "source_turn_id = ?", (str(world.turns["main"]),)
    ) == 0
    assert _count(
        db,
        "review_event",
        "review_event_id = ?",
        (world.review_event_id,),
    ) == 0
    assert _count(
        db,
        "relationship_memory",
        "relationship_memory_id = ?",
        (world.memories["main"],),
    ) == 0
    assert execution.tombstoned > 0
    assert execution.cleared_provenance_legs >= 1


def test_conversation_deletion_leaves_the_sibling_conversations_alone(
    db: sqlite3.Connection, world: World, deletion_controller
) -> None:
    """SEC-019 is scoped to *this* conversation, never to the user."""

    result = deletion_controller.execute(
        DeletionRequest(
            scope=DeletionScope.CONVERSATION, conversation_id=CONV
        )
    )
    assert isinstance(result, Ok), result

    for key, conversation_id in (
        ("other", CONV_OTHER),
        ("foreign", CONV_OTHER_PERSONA),
    ):
        assert _count(
            db, "conversation", "conversation_id = ?", (str(conversation_id),)
        ) == 1
        assert _count(
            db, "turn_record", "conversation_id = ?", (str(conversation_id),)
        ) == 1
        assert _count(
            db, "episode", "conversation_id = ?", (str(conversation_id),)
        ) == 1
        assert _count(
            db,
            "relationship_memory",
            "relationship_memory_id = ?",
            (world.memories[key],),
        ) == 1
    # The user's own setting survives; only its unresolvable leg is cleared.
    row = db.execute(
        "SELECT created_from_turn_id FROM planner_constraint"
        " WHERE constraint_id = ?",
        (world.constraint_id,),
    ).fetchone()
    assert row is not None and row[0] is None


def test_conversation_deletion_leaves_the_profile_columns_byte_identical(
    db: sqlite3.Connection, world: World, deletion_controller
) -> None:
    """§19's profile leg, pinned as the registered gap it is (F2).

    §19 asks for the "Profile fact solely derived from C" to be deleted along
    provenance. ``user_profile`` carries no per-fact provenance column (§5.1
    freezes the column set, §17's ask included), so this scope cannot decide
    *solely derived* for a fact and touches no profile row — which is exactly
    why the negative is worth pinning: a later cut that starts rewriting
    profile rows on a conversation deletion would fail here and would have to
    arrive with a decision behind it (the same reading as
    ``elc/deletion/__init__.py``'s registration of the gap). The four content
    columns are compared row-wise and byte-for-byte; the row's identity and
    its §1.4 stamp are covered by the configuration-table probe below, which
    compares the whole row.
    """

    before = db.execute(
        "SELECT revision, profile_facts, preferences, settings"
        " FROM user_profile"
    ).fetchall()
    assert before, "the world carries a profile row"

    result = deletion_controller.execute(
        DeletionRequest(
            scope=DeletionScope.CONVERSATION, conversation_id=CONV
        )
    )
    assert isinstance(result, Ok), result

    after = db.execute(
        "SELECT revision, profile_facts, preferences, settings"
        " FROM user_profile"
    ).fetchall()
    assert after == before


def test_conversation_deletion_invalidates_but_keeps_the_schedule_row(
    db: sqlite3.Connection, world: World, deletion_controller
) -> None:
    """§19's "review history rebuilt": the row stays and is recomputed."""

    result = deletion_controller.execute(
        DeletionRequest(
            scope=DeletionScope.CONVERSATION, conversation_id=CONV
        )
    )
    assert isinstance(result, Ok), result
    assert _count(
        db,
        "schedule_item",
        "schedule_item_id = ?",
        (world.schedule_item_id,),
    ) == 1


# ---------------------------------------------------------------------------
# §20 LEARNING_TARGET — positive and counter-example
# ---------------------------------------------------------------------------


def test_learning_target_deletion_removes_the_targets_learning_rows(
    db: sqlite3.Connection, world: World, deletion_controller
) -> None:
    result = deletion_controller.execute(
        DeletionRequest(
            scope=DeletionScope.LEARNING_TARGET, target_id=TARGET_ID
        )
    )
    assert isinstance(result, Ok), result

    assert _count(db, "evidence_claim", "target_id = ?", (str(TARGET_ID),)) == 0
    assert _count(
        db, "learner_target_state", "target_id = ?", (str(TARGET_ID),)
    ) == 0
    assert _count(
        db, "schedule_item", "target_id = ?", (str(TARGET_ID),)
    ) == 0
    assert _count(db, "review_event") == 0


def test_learning_target_deletion_keeps_the_transcript_and_the_pair(
    db: sqlite3.Connection, world: World, deletion_controller
) -> None:
    """SEC-026: learning deletion does not touch Relationship data, and §20
    keeps the transcript. The user's own setting is not learning history."""

    result = deletion_controller.execute(
        DeletionRequest(
            scope=DeletionScope.LEARNING_TARGET, target_id=TARGET_ID
        )
    )
    assert isinstance(result, Ok), result

    assert _count(db, "conversation") == 3
    assert _count(db, "turn_record") == 3
    assert _count(db, "user_turn") == 3
    assert _count(db, "relationship_memory") == 3
    assert _count(db, "user_profile") == 1
    row = db.execute(
        "SELECT created_from_turn_id FROM planner_constraint"
        " WHERE constraint_id = ?",
        (world.constraint_id,),
    ).fetchone()
    assert row is not None and row[0] == str(world.turns["main"])


# ---------------------------------------------------------------------------
# §20 ALL_LEARNING_HISTORY — positive and counter-example
# ---------------------------------------------------------------------------


def test_all_learning_history_removes_every_learning_row(
    db: sqlite3.Connection, world: World, deletion_controller
) -> None:
    from elc.deletion.types import LEARNING_HISTORY_SWEPT_TABLES

    result = deletion_controller.execute(
        DeletionRequest(scope=DeletionScope.ALL_LEARNING_HISTORY)
    )
    assert isinstance(result, Ok), result

    for table in LEARNING_HISTORY_SWEPT_TABLES:
        assert _count(db, table) == 0, table


def test_all_learning_history_keeps_conversation_relationship_profile_goals(
    db: sqlite3.Connection, world: World, deletion_controller
) -> None:
    """§20's keep list, asserted one table at a time."""

    result = deletion_controller.execute(
        DeletionRequest(scope=DeletionScope.ALL_LEARNING_HISTORY)
    )
    assert isinstance(result, Ok), result

    assert _count(db, "conversation") == 3
    assert _count(db, "turn_record") == 3
    assert _count(db, "relationship_memory") == 3
    assert _count(db, "user_profile") == 1
    assert _count(db, "planner_constraint") == 1
    assert _count(db, "teaching_policy") == 0  # never written in this world
    assert _count(db, "goal_portfolio") == 0  # never written in this world


# ---------------------------------------------------------------------------
# §21 RELATIONSHIP_PAIR — positive and counter-example
# ---------------------------------------------------------------------------


def test_relationship_pair_deletion_removes_that_pairs_memories(
    db: sqlite3.Connection, world: World, deletion_controller
) -> None:
    result = deletion_controller.execute(
        DeletionRequest(scope=DeletionScope.RELATIONSHIP_PAIR, persona_id=PERSONA)
    )
    assert isinstance(result, Ok), result

    assert _count(
        db, "relationship_memory", "persona_id = ?", (str(PERSONA),)
    ) == 0
    assert _count(
        db, "relationship_memory", "persona_id = ?", (str(PERSONA_OTHER),)
    ) == 1


def test_relationship_pair_deletion_keeps_learning_and_transcript(
    db: sqlite3.Connection, world: World, deletion_controller
) -> None:
    """SEC-027: relationship deletion does not silently delete Learning data
    (§21's "不自动删除" list), and the transcript stays."""

    result = deletion_controller.execute(
        DeletionRequest(scope=DeletionScope.RELATIONSHIP_PAIR, persona_id=PERSONA)
    )
    assert isinstance(result, Ok), result

    assert _count(db, "conversation") == 3
    assert _count(db, "turn_record") == 3
    assert _count(db, "evidence_claim") >= 1
    assert _count(db, "evidence_group") >= 1
    assert _count(db, "user_profile") == 1


def test_relationship_pair_deletion_rebuilds_the_episode_projection(
    db: sqlite3.Connection, world: World, deletion_controller
) -> None:
    """§18's rebuild clause through the shipped CP4 path, not a second one.

    The episode row survives (invalidation, not removal) and its job row is
    released so the shipped executor re-derives it; the rebuild reports Ok.
    """

    result = deletion_controller.execute(
        DeletionRequest(scope=DeletionScope.RELATIONSHIP_PAIR, persona_id=PERSONA)
    )
    assert isinstance(result, Ok), result
    outcome = result.value

    episodes = [
        attempt for attempt in outcome.rebuilds if attempt.kind == "EPISODE"
    ]
    assert episodes, "the pair's conversations must be re-projected"
    assert all(attempt.ok for attempt in episodes), episodes
    # The row is still there — invalidated-and-rebuilt, never deleted.
    assert _count(db, "episode") == 3
    # And no deleted memory text survives inside the projection's open_threads.
    rows = db.execute("SELECT open_threads FROM episode").fetchall()
    assert all(MAIN_MEMORY not in str(row[0]) for row in rows)


# ---------------------------------------------------------------------------
# benchmark S44 PROFILE_FIELD — positive and counter-example
# ---------------------------------------------------------------------------


def test_profile_field_deletion_clears_the_fact_set(
    db: sqlite3.Connection, world: World, deletion_controller
) -> None:
    result = deletion_controller.execute(
        DeletionRequest(scope=DeletionScope.PROFILE_FIELD, field_key="city")
    )
    assert isinstance(result, Ok), result

    row = db.execute(
        "SELECT profile_facts, revision FROM user_profile"
    ).fetchone()
    assert row is not None
    assert json.loads(str(row[0])) == []
    assert str(row[1]) != "rev-1", "the §1.4 stamp must move with the content"


def test_profile_field_deletion_keeps_preferences_settings_and_transcript(
    db: sqlite3.Connection, world: World, deletion_controller
) -> None:
    result = deletion_controller.execute(
        DeletionRequest(scope=DeletionScope.PROFILE_FIELD, field_key="city")
    )
    assert isinstance(result, Ok), result

    row = db.execute(
        "SELECT preferences, settings FROM user_profile"
    ).fetchone()
    assert row is not None
    assert json.loads(str(row[0])) == ["concise explanations"]
    assert json.loads(str(row[1])) == ["dark mode"]
    assert _count(db, "turn_record") == 3
    assert _count(db, "relationship_memory") == 3


# ---------------------------------------------------------------------------
# §22 PERSONA_PACKAGE — the empty app.db face, and no widening
# ---------------------------------------------------------------------------


def test_persona_package_deletes_nothing_in_app_db(
    db: sqlite3.Connection, world: World, deletion_controller
) -> None:
    result = deletion_controller.execute(
        DeletionRequest(scope=DeletionScope.PERSONA_PACKAGE, persona_id=PERSONA)
    )
    assert isinstance(result, Ok), result
    assert result.value.execution.tallies == ()
    assert result.value.execution.tombstoned == 0
    assert any("app.db" in note for note in result.value.notes)


def test_persona_package_does_not_widen_to_the_transcript_or_the_pair(
    db: sqlite3.Connection, world: World, deletion_controller
) -> None:
    """§22: "是否删除历史 transcript 必须由用户单独选择，不能暗中扩大删除范围"."""

    result = deletion_controller.execute(
        DeletionRequest(scope=DeletionScope.PERSONA_PACKAGE, persona_id=PERSONA)
    )
    assert isinstance(result, Ok), result

    assert _count(db, "conversation") == 3
    assert _count(db, "turn_record") == 3
    assert _count(db, "relationship_memory") == 3
    assert _count(db, "episode") == 3


# ---------------------------------------------------------------------------
# §23 ALL_USER_DATA — positive and counter-example
# ---------------------------------------------------------------------------


def test_all_user_data_sweeps_every_user_table(
    db: sqlite3.Connection, world: World, deletion_controller
) -> None:
    from elc.deletion.types import ALL_USER_DATA_SWEPT_TABLES

    result = deletion_controller.execute(
        DeletionRequest(scope=DeletionScope.ALL_USER_DATA)
    )
    assert isinstance(result, Ok), result

    for table in ALL_USER_DATA_SWEPT_TABLES:
        assert _count(db, table) == 0, table
    assert result.value.execution.tombstoned > 0


def test_all_user_data_keeps_the_infrastructure_and_the_ledger(
    db: sqlite3.Connection, world: World, deletion_controller
) -> None:
    """SEC-025 in this repository's shape, plus §23's kept ledger."""

    stamps_before = dict(
        db.execute(
            "SELECT key, value FROM schema_meta"
            " WHERE key LIKE '%schema_version%'"
        ).fetchall()
    )
    result = deletion_controller.execute(
        DeletionRequest(scope=DeletionScope.ALL_USER_DATA)
    )
    assert isinstance(result, Ok), result

    assert dict(
        db.execute(
            "SELECT key, value FROM schema_meta"
            " WHERE key LIKE '%schema_version%'"
        ).fetchall()
    ) == stamps_before
    # 18 = the applied lineage through P9-1's 0018_delivery_records (the
    # head count; the pin moved 14 → 15 with P8-0's 0015_planner_records,
    # 15 → 16 with P8-3's 0016_planning_ledger, 16 → 17 with P8-4's
    # 0017_ledger_event_provenance, and 17 → 18 with this migration).
    assert _count(db, "schema_migrations") == 18
    assert _count(db, "runtime_epoch") == 1
    assert _count(db, "deletion_tombstone") > 0


def test_all_user_data_never_touches_the_global_content_db(
    world: World, deletion_controller, built_content_db: Path
) -> None:
    """SEC-025 behaviourally: content.db is another file and stays byte-identical."""

    result = deletion_controller.execute(
        DeletionRequest(scope=DeletionScope.ALL_USER_DATA)
    )
    assert isinstance(result, Ok), result
    assert _digest(built_content_db) == world.content_digest


# ---------------------------------------------------------------------------
# §5.1 configuration — a scope leaves every table it does not name untouched
# ---------------------------------------------------------------------------
#
# The "declaration face vs execution face" pin (review F3 / mutation m7): the
# surfaces *declare* which tables a scope may reach, and the probes above
# assert the rows the cases name. What none of them asserted is the other
# half — that a scope's execution does not reach for a §5.1 configuration
# table its declaration never names. A stray ``DELETE FROM user_profile``
# inside the conversation walk was invisible to this suite (zero RED), which
# is what this section closes.
#
# The map below is the *whole* truth, one entry per scope, so a scope whose
# surface grows one of these tables fails the structural pin instead of
# quietly shrinking the behavioural probe's coverage. Four of the five tables
# are user-level (§5.1 pins no owner column; Local V1 keys them by the user's
# own id). ``session_focus`` is keyed to a conversation — §5.1 spells its
# ``conversation_id`` NOT NULL and a foreign key to ``conversation`` — which
# is why the CONVERSATION scope, and only that scope, reaches for the focus
# rows of the conversations it removes.

CONFIGURATION_TABLES: tuple[str, ...] = (
    "user_profile",
    "disclosure_policy",
    "goal_portfolio",
    "teaching_policy",
    "session_focus",
)

CONFIGURATION_TABLES_TOUCHED: dict[DeletionScope, tuple[str, ...]] = {
    DeletionScope.CONVERSATION: ("session_focus",),
    DeletionScope.LEARNING_TARGET: (),
    DeletionScope.ALL_LEARNING_HISTORY: (),
    DeletionScope.RELATIONSHIP_PAIR: (),
    DeletionScope.PROFILE_FIELD: ("user_profile",),
    DeletionScope.PERSONA_PACKAGE: (),
    DeletionScope.ALL_USER_DATA: CONFIGURATION_TABLES,
}


def _configuration_rows(
    db: sqlite3.Connection,
) -> dict[str, list[tuple[object, ...]]]:
    """Every row of every configuration table, whole-row and in rowid order.

    Whole-row on purpose: a scope that rewrote one column of one of these
    rows (a stamp, a leg) would slip past a row count, and this probe is the
    one that has to see it.
    """

    return {
        table: [
            tuple(row)
            for row in db.execute(f"SELECT * FROM {table} ORDER BY rowid")
        ]
        for table in CONFIGURATION_TABLES
    }


def _write_configuration(user_config_store) -> None:
    """One live row per configuration table, through the shipped write faces.

    Not a seed helper: these are the §5.1 write faces themselves, and they are
    here because the world fixture carries only a profile — a probe that
    compared three empty tables against three empty tables would be as blind
    as the assertion it replaces.
    """

    focus_inputs = (
        ("sf-main", CONV),
        ("sf-other", CONV_OTHER),
    )
    for focus_id, conversation in focus_inputs:
        written = user_config_store.set_session_focus(
            SessionFocus(
                session_focus_id=focus_id,
                conversation_id=conversation,
                base_goal_portfolio_version=GoalVersion("gv-1"),
                temporary_goal_weights={GoalModality.SPEAKING: 1.0},
                manual_focus_target=None,
                starts_at="2026-09-22T09:00:00+00:00",
                expires_at=None,
            )
        )
        assert isinstance(written, Ok), written

    policy = user_config_store.set_disclosure_policy(
        DisclosurePolicy(
            disclosure_policy_id=str(USER),
            revision="pol-1",
            rules=(
                DisclosureRule(
                    persona_id=None,
                    disclosure_level=DisclosureLevel.FUNCTIONAL,
                ),
            ),
        )
    )
    assert isinstance(policy, Ok), policy

    portfolio = user_config_store.upsert_goal_portfolio(
        LearningGoalPortfolio(
            goal_portfolio_id=USER,
            goal_version=GoalVersion("gv-1"),
            assessment_targets=("ielts-speaking",),
            register_style_goals=("workplace-formal",),
            effective_from="2026-09-22T00:00:00+00:00",
        )
    )
    assert isinstance(portfolio, Ok), portfolio

    teaching = user_config_store.upsert_teaching_policy(
        TeachingPolicyProfile(
            teaching_policy_profile_id=USER,
            policy_version=PolicyVersion("pv-1"),
            teaching_frequency=TeachingFrequency.BALANCED,
        )
    )
    assert isinstance(teaching, Ok), teaching


def _configuration_request(scope: DeletionScope) -> DeletionRequest:
    """The key-carrying request for each scope this section deletes under."""

    if scope is DeletionScope.CONVERSATION:
        return DeletionRequest(scope=scope, conversation_id=CONV)
    if scope is DeletionScope.LEARNING_TARGET:
        return DeletionRequest(scope=scope, target_id=TARGET_ID)
    if scope is DeletionScope.RELATIONSHIP_PAIR:
        return DeletionRequest(scope=scope, persona_id=PERSONA)
    raise AssertionError(f"{scope} is not a scope this probe covers")


@pytest.mark.parametrize("scope", sorted(DeletionScope, key=lambda s: s.value))
def test_the_configuration_tables_a_scope_names_are_the_declared_ones(
    scope: DeletionScope,
) -> None:
    """The map above is the whole truth, held against the two declarations.

    A scope that started naming one of these tables (or stopped naming one it
    names today) fails here, so the behavioural probe's "untouched" set can
    never widen by accident — the exclusion is declared, not inferred from
    whatever the implementation happens to do.
    """

    assert set(CONFIGURATION_TABLES_TOUCHED) == set(DeletionScope)
    named = set(CONFIGURATION_TABLES) & set(SCOPE_SWEPT_TABLES[scope])
    assert named == set(CONFIGURATION_TABLES_TOUCHED[scope]), scope.value


@pytest.mark.parametrize(
    "scope",
    (
        DeletionScope.CONVERSATION,
        DeletionScope.LEARNING_TARGET,
        DeletionScope.RELATIONSHIP_PAIR,
    ),
)
def test_a_scope_leaves_the_configuration_tables_it_does_not_name(
    scope: DeletionScope,
    db: sqlite3.Connection,
    world: World,
    user_config_store,
    deletion_controller,
) -> None:
    """Rows and content, not just counts: the negative half of every surface.

    Each scope is probed over the same five live rows; what it must leave
    behind is compared **whole-row** before and after, and the non-vacuity leg
    (every table it must leave holds a row) is what makes the comparison
    able to fail — a table that was empty before and after proves nothing.
    """

    _write_configuration(user_config_store)
    before = _configuration_rows(db)
    untouched = tuple(
        table
        for table in CONFIGURATION_TABLES
        if table not in CONFIGURATION_TABLES_TOUCHED[scope]
    )
    assert all(before[table] for table in untouched), untouched

    result = deletion_controller.execute(_configuration_request(scope))
    assert isinstance(result, Ok), result

    after = _configuration_rows(db)
    for table in untouched:
        assert after[table] == before[table], table
    for table in CONFIGURATION_TABLES_TOUCHED[scope]:
        assert after[table] != before[table], table

    if scope is DeletionScope.CONVERSATION:
        # The one table this scope does name is named for exactly its own
        # conversation: the sibling's focus row is not the deletion's to take
        # (the same counter-example the sibling probes hold for turns and
        # memories).
        remaining = db.execute(
            "SELECT conversation_id FROM session_focus ORDER BY rowid"
        ).fetchall()
        assert [str(row[0]) for row in remaining] == [str(CONV_OTHER)]
