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

from elc.deletion.types import (
    DeletionRequest,
    DeletionScope,
)
from elc.platform.types import Ok
from tests.deletion.conftest import (
    CONV,
    CONV_OTHER,
    CONV_OTHER_PERSONA,
    MAIN_MEMORY,
    PERSONA,
    PERSONA_OTHER,
    TARGET_ID,
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
    assert _count(db, "schema_migrations") == 14
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
