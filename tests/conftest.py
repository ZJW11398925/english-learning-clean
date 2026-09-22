"""Shared test fixtures / paths."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from elc.platform.db.decision_cycle_store import SqliteDecisionCycleStore
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.db.generation_store import SqliteGenerationStore

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src" / "elc"
DOCS_ROOT = REPO_ROOT / "docs"
BASELINES = REPO_ROOT / "behavioral_baselines"

# ---------------------------------------------------------------------------
# The migration lineage, declared once
# ---------------------------------------------------------------------------
#
# Every phase's migration pins spelled the lineage out per file (the applied-id
# list, the head file name, the stamped version). That made each new migration
# a mechanical edit in a dozen suites — the kind of change a hand copy gets
# subtly wrong — so the lineage lives here and the suites reference it. Each
# pin keeps its own historical comment, and
# tests/architecture/test_platform_db_infra.py pins these three constants
# against the real ``migrations/`` directory and against the stamp a fresh
# database carries, so they cannot become a rubber stamp for themselves.

#: Every migration id, in filename order (the runner is filename-ordered).
MIGRATION_IDS: tuple[str, ...] = (
    "0001_bootstrap",
    "0002_conversation_core",
    "0003_generation_provider",
    "0004_learning_evidence",
    "0005_learner_target_state",
    "0006_decision_cycle",
    "0007_teaching_lineage",
    "0008_attempt_records",
    "0009_relationship_contracts",
    "0010_episode_and_user_config",
    "0011_goal_policy_focus",
    "0012_schedule_review",
    "0013_planner_constraint",
    "0014_deletion_tombstone",
)

#: The newest migration's file name, and the ``schema_version`` /
#: ``runtime_schema_version`` stamp that applying the whole chain leaves.
SCHEMA_HEAD_FILE = "0014_deletion_tombstone.sql"
SCHEMA_HEAD_VERSION = "14"

# Phase 0 packages: the domains from docs/IMPLEMENTATION_PLAN.md §2 plus
# the User Configuration/Profile bounded context (docs/DOMAIN_MODEL.md
# §5.1) and the World/Lore bounded context (docs/DOMAIN_MODEL.md §2
# Authority Matrix / §1 domain map). platform is the shared kernel, not a
# domain.
DOMAIN_PACKAGES = (
    "conversation",
    "persona",
    "relationship",
    "learning",
    "curriculum",
    "scheduler",
    "planner",
    "teaching",
    "runtime",
    "content",
    "user_config",
    "world_lore",
)


class AssemblyGenerationStore(SqliteGenerationStore):
    """Test assembly store: the generation store plus the sibling
    Runtime-owned DecisionCycle store over the same app.db connection and
    epoch fence.

    Migration 0007 tightens ``generation_action_intent.decision_cycle_id``
    to NOT NULL + FK(decision_cycle): every generation action belongs to a
    decision cycle, so every assembly that drives a turn needs both
    stores. The phase fixtures are the single wiring point (they build the
    pair once), which keeps the shipped P1/P2/P3 test bodies — and their
    ``make_coordinator`` helpers — unchanged. Production assemblies inject
    the two stores explicitly (see ConversationCoordinator's constructor);
    this class exists only inside the test suite.
    """

    decision_cycles: SqliteDecisionCycleStore

    def __init__(self, conn: sqlite3.Connection, fence: RuntimeEpochFence) -> None:
        super().__init__(conn, fence)
        self.decision_cycles = SqliteDecisionCycleStore(conn, fence)
