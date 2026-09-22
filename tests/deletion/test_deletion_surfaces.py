"""Gate 2 ③ — the scope surfaces, the §23 table closure, and the identity.

Three kinds of claim live here, and all three are checkable rather than
promised:

- **the sweep is closed** — the three declared table sets partition every
  table of a freshly migrated app.db, so a later migration cannot add a table
  that ALL_USER_DATA would silently walk past (and the runtime guard refuses
  one that appears anyway);
- **the isolation invariants are structural** — SEC-026 and SEC-027 are
  statements about disjoint table sets, not about behaviour;
- **§24's identity is deterministic and one-way** — the same entity yields the
  same ledger id across processes, the kind is bound into the digest, and the
  id itself is not recoverable from what the ledger stores.
"""

from __future__ import annotations

import sqlite3

import pytest

from elc.deletion.plan import (
    ENTITY_FIELD_SEPARATOR,
    UnknownTableError,
    assert_known_tables,
    entity_hash_for,
    is_tombstoned,
    tombstone_id_for,
)
from elc.deletion.types import (
    ALL_USER_DATA_SWEPT_TABLES,
    CONVERSATION_SWEPT_TABLES,
    DELETION_POLICY_VERSION,
    GLOBAL_CONTENT_TABLES,
    LEARNING_HISTORY_SWEPT_TABLES,
    LEARNING_TARGET_SWEPT_TABLES,
    PERSONA_PACKAGE_SWEPT_TABLES,
    PROFILE_FIELD_SWEPT_TABLES,
    RELATIONSHIP_PAIR_SWEPT_TABLES,
    RETAINED_TABLES,
    SCOPE_SWEPT_TABLES,
    SWEPT_TABLES,
    DeletionRequest,
    DeletionScope,
)
from elc.platform.types import Err


def _tables(db: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
            " AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    }


# -- §23's closure ---------------------------------------------------------


def test_the_three_sets_partition_the_real_database(
    db: sqlite3.Connection,
) -> None:
    """The pin §23 needs: every table of a migrated app.db is classified.

    A migration that lands a table without deciding whether the sweep removes
    it fails here — which is the only way "ALL_USER_DATA deletes all user
    records" stays true as the schema grows.
    """

    declared = (
        set(SWEPT_TABLES)
        | set(RETAINED_TABLES)
        | set(GLOBAL_CONTENT_TABLES)
    )
    assert declared == _tables(db)
    assert len(SWEPT_TABLES) + len(RETAINED_TABLES) + len(
        GLOBAL_CONTENT_TABLES
    ) == len(declared), "the three sets overlap"


def test_the_runtime_guard_agrees_with_the_pin(db: sqlite3.Connection) -> None:
    assert_known_tables(sorted(_tables(db)))


def test_an_unclassified_table_is_refused(db: sqlite3.Connection) -> None:
    db.execute("CREATE TABLE rogue_user_table (id TEXT PRIMARY KEY)")
    with pytest.raises(UnknownTableError) as excinfo:
        assert_known_tables(sorted(_tables(db)))
    assert "rogue_user_table" in str(excinfo.value)


def test_the_all_user_data_sweep_fails_on_an_unclassified_table(
    db: sqlite3.Connection, deletion_store
) -> None:
    """The guard runs *inside* the deletion transaction, before any write."""

    db.execute("CREATE TABLE rogue_user_table (id TEXT PRIMARY KEY)")
    db.execute("INSERT INTO rogue_user_table VALUES ('x')")
    db.commit()
    result = deletion_store.execute(
        DeletionRequest(scope=DeletionScope.ALL_USER_DATA)
    )
    assert isinstance(result, Err)
    # Nothing was written: the refusal is not a partial sweep.
    assert db.execute("SELECT COUNT(*) FROM rogue_user_table").fetchone() == (
        1,
    )
    assert db.execute(
        "SELECT COUNT(*) FROM deletion_tombstone"
    ).fetchone() == (0,)
    db.execute("DROP TABLE rogue_user_table")


def test_the_retained_set_is_the_four_infrastructure_and_ledger_tables() -> None:
    assert set(RETAINED_TABLES) == {
        "deletion_tombstone",
        "runtime_epoch",
        "schema_meta",
        "schema_migrations",
    }


def test_no_global_content_table_lives_in_app_db() -> None:
    """SEC-025 in this repository's shape: the kept assets are content.db's.

    The set is empty *on purpose* — global curriculum and content live in a
    separate read-only artifact, so no app.db table may be claimed as global —
    and the sweep's closure is what makes the rule enforceable (nothing
    unnamed can be swept).
    """

    assert GLOBAL_CONTENT_TABLES == ()


# -- the per-scope surfaces ------------------------------------------------


def test_every_scope_surface_is_a_subset_of_the_swept_tables() -> None:
    for surface in SCOPE_SWEPT_TABLES.values():
        assert set(surface) <= set(SWEPT_TABLES)


def test_every_scope_has_a_surface_declaration() -> None:
    assert set(SCOPE_SWEPT_TABLES) == set(DeletionScope)


def test_learning_deletion_never_names_a_relationship_table() -> None:
    """SEC-026: learning deletion does not silently delete Relationship data."""

    for surface in (
        LEARNING_TARGET_SWEPT_TABLES,
        LEARNING_HISTORY_SWEPT_TABLES,
        ALL_USER_DATA_SWEPT_TABLES,
    ):
        if surface is ALL_USER_DATA_SWEPT_TABLES:
            # The whole-user scope legitimately removes everything; SEC-026 is
            # about the *learning* scopes, which is why it is checked on the
            # two above and only noted here.
            continue
        assert "relationship_memory" not in surface


def test_relationship_deletion_never_names_a_learning_table() -> None:
    """SEC-027: relationship deletion does not silently delete Learning data."""

    for table in (
        "analysis_artifact",
        "evidence_claim",
        "evidence_commit",
        "evidence_group",
        "learner_self_report",
        "learner_target_state",
        "learning_opportunity_record",
        "review_event",
        "schedule_item",
        "teaching_moment",
        "attempt_record",
        "attempt_evaluation_record",
        "decision_cycle",
    ):
        assert table not in RELATIONSHIP_PAIR_SWEPT_TABLES, table


def test_the_conversation_surface_keeps_the_users_own_settings() -> None:
    """§19's closure is about derived state, not about §9 settings.

    ``goal_portfolio`` / ``teaching_policy`` / ``user_profile`` /
    ``disclosure_policy`` are the user's own configuration (§5.1) and no
    section of §19–§23 names them; ``planner_constraint`` appears only because
    its ``created_from_turn_id`` leg must be cleared, never because the row is
    deleted.
    """

    for table in (
        "goal_portfolio",
        "teaching_policy",
        "user_profile",
        "disclosure_policy",
    ):
        assert table not in CONVERSATION_SWEPT_TABLES
    assert "planner_constraint" in CONVERSATION_SWEPT_TABLES


def test_the_persona_package_surface_is_empty_in_v1() -> None:
    """§22: no persona definition table exists in app.db, so nothing may be
    reached for on this scope's behalf."""

    assert PERSONA_PACKAGE_SWEPT_TABLES == ()


def test_the_profile_field_surface_is_the_profile_row() -> None:
    assert PROFILE_FIELD_SWEPT_TABLES == ("user_profile",)


def test_learning_target_keeps_the_transcript() -> None:
    for table in (
        "conversation",
        "turn_record",
        "user_turn",
        "assistant_turn",
        "input_envelope",
    ):
        assert table not in LEARNING_TARGET_SWEPT_TABLES, table


# -- the sweep order -------------------------------------------------------


def test_the_sweep_order_is_children_first(db: sqlite3.Connection) -> None:
    """The declared order satisfies every foreign key the schema carries.

    Checked against ``PRAGMA foreign_key_list`` rather than by trying a
    delete: at each position, no *later* table may reference the one being
    removed (self-references are the two allowed loops, and both are handled
    by a table-wide delete).
    """

    positions = {table: index for index, table in enumerate(SWEPT_TABLES)}
    violations: list[str] = []
    for table in SWEPT_TABLES:
        for row in db.execute(f"PRAGMA foreign_key_list({table})").fetchall():
            parent = str(row[2])
            if parent == table or parent not in positions:
                continue
            if positions[parent] < positions[table]:
                violations.append(f"{table} references {parent} too late")
    assert not violations, violations


def test_the_all_user_data_sweep_is_the_declared_order() -> None:
    assert ALL_USER_DATA_SWEPT_TABLES == SWEPT_TABLES
    assert len(set(SWEPT_TABLES)) == len(SWEPT_TABLES)


def test_every_scope_surface_is_children_first(db: sqlite3.Connection) -> None:
    """Each scope's own order satisfies every foreign key inside that surface.

    The whole-database sweep has its own pin above; this one covers the
    narrower walks (ALL_LEARNING_HISTORY above all), because a surface that
    lists a parent before its child fails at run time with an opaque
    ``FOREIGN KEY constraint failed`` — which is exactly how this was found.
    """

    violations: list[str] = []
    for scope, surface in SCOPE_SWEPT_TABLES.items():
        positions = {table: index for index, table in enumerate(surface)}
        for table in surface:
            for row in db.execute(
                f"PRAGMA foreign_key_list({table})"
            ).fetchall():
                parent = str(row[2])
                if parent == table or parent not in positions:
                    continue
                if positions[parent] < positions[table]:
                    violations.append(
                        f"{scope.value}: {table} references {parent} too late"
                    )
    assert not violations, violations


def test_every_scope_surface_follows_the_global_order() -> None:
    """A scoped walk keeps the relative order the whole-database walk uses.

    Holds for the *subsequences*: the two whole-walk surfaces and the scoped
    declarations are all children-first, so their tables appear in
    :data:`SWEPT_TABLES` order. (The relation is one-way on purpose — a
    children-first order need not be a subsequence — but every surface this
    package ships happens to satisfy the stronger form, and a surface that
    stopped satisfying it would be worth a second look.)
    """

    global_positions = {
        table: index for index, table in enumerate(SWEPT_TABLES)
    }
    for scope, surface in SCOPE_SWEPT_TABLES.items():
        positions = [global_positions[table] for table in surface]
        assert positions == sorted(positions), scope.value


# -- §24's identity --------------------------------------------------------


def test_the_entity_hash_is_a_full_sha256_over_kind_and_id() -> None:
    digest = entity_hash_for("conversation", "c1")
    assert len(digest) == 64
    assert all(character in "0123456789abcdef" for character in digest)


def test_the_kind_is_bound_into_the_digest() -> None:
    assert entity_hash_for("conversation", "c1") != entity_hash_for(
        "turn_record", "c1"
    )


def test_the_digest_is_deterministic_across_calls() -> None:
    assert entity_hash_for("conversation", "c1") == entity_hash_for(
        "conversation", "c1"
    )


def test_the_digest_does_not_carry_the_id() -> None:
    """§24's opaqueness: the ledger must not be readable as an id list."""

    digest = entity_hash_for("conversation", "conv-del-1")
    assert "conv-del-1" not in digest


def test_the_field_separator_is_the_repository_unit_separator() -> None:
    assert ENTITY_FIELD_SEPARATOR == "\x1f"


def test_the_tombstone_id_is_derived_from_the_identity() -> None:
    digest = entity_hash_for("conversation", "c1")
    first = tombstone_id_for("conversation", digest)
    second = tombstone_id_for("conversation", digest)
    assert first == second
    assert first.startswith("ts-")
    assert len(first) == len("ts-") + 20


def test_the_predicate_answers_from_a_hashed_ledger() -> None:
    ledger = {("conversation", entity_hash_for("conversation", "c1"))}
    assert is_tombstoned(ledger, entity_kind="conversation", entity_id="c1")
    assert not is_tombstoned(ledger, entity_kind="conversation", entity_id="c2")
    assert not is_tombstoned(ledger, entity_kind="turn_record", entity_id="c1")


def test_the_policy_version_is_not_the_schema_version() -> None:
    """§24's ``scope_version`` versions the deletion rules, not the schema."""

    assert DELETION_POLICY_VERSION == "deletion-policy-v1"


def test_the_package_imports_from_a_cold_interpreter() -> None:
    """The cold-start rule (P4-3's lesson), pinned for this package.

    ``elc.deletion`` is a cross-package face — it reaches Learning, Scheduler
    and the CP4 runtime through *ports* — so a cold ``import elc.deletion``
    must work on its own, and so must a cold ``import elc.runtime`` beside it
    (the import-cycle shape that once broke ``import elc.conversation``).
    """

    import subprocess
    import sys

    for module in ("elc.deletion", "elc.runtime", "elc.learning", "elc.scheduler"):
        proc = subprocess.run(
            [sys.executable, "-c", f"import {module}"],
            capture_output=True,
            text=True,
            cwd="src",
        )
        assert proc.returncode == 0, f"{module}: {proc.stderr}"


def test_the_controller_carries_no_sql() -> None:
    """The authority face is SQL-free (the user_config / scheduler precedent:
    every statement lives in the store)."""

    from tests.conftest import SRC_ROOT
    from tests.phase3.sql_write_scan import write_targets

    assert write_targets(SRC_ROOT / "deletion" / "controller.py") == set()
    assert write_targets(SRC_ROOT / "deletion" / "plan.py") == set()
    assert write_targets(SRC_ROOT / "deletion" / "types.py") == set()


def test_the_statement_scan_and_the_table_scan_agree_on_the_store() -> None:
    """The two readers of one fold see the same table set (Gate 2 review F5).

    ``write_statements`` anchors a statement at the start of its literal —
    which is what keeps prose from being read as one — while ``write_targets``
    matches anywhere in a folded literal. The only difference they may show on
    this module is the artifact the anchor exists for: the module docstring's
    "the ordinary create/update verbs stay with …" sentence, whose
    ``update verbs`` reads as an ``UPDATE`` on a table called ``verbs``. Every
    other divergence — a statement the anchored reader cannot see — fails
    here, so swapping the compensation assertions onto the verb-aware reader
    cannot have narrowed what they cover.
    """

    from tests.conftest import SRC_ROOT
    from tests.phase3.sql_write_scan import write_statements, write_targets

    store = SRC_ROOT / "deletion" / "store.py"
    statements = set(write_statements(store))
    targets = write_targets(store)
    assert statements <= targets
    assert targets - statements == {"verbs"}
