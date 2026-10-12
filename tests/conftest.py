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
    "0015_planner_records",
    "0016_planning_ledger",
    "0017_ledger_event_provenance",
    "0018_delivery_records",
    # MC-0 (DEC-OPI-a31b14c9…43): the user-authored character card — the
    # zero-migration stretch ends here on the user's call (user-created
    # characters persist).
    "0019_character_cards",
    # 主线-3 (DEC-OPI-32409938…36): the World/Lore canonical facts — the
    # table the persona prompt's [lore] section is rendered from.
    "0020_world_lore_facts",
    # fr-A (frontend revamp cut A): the provider-reported token usage
    # counters as three adjudicated ProviderAttempt columns (the owner_epoch
    # precedent — a fact of the attempt, no new table). Renumbered 0020→0021
    # at merge: master's 0020_world_lore_facts merged first (the
    # first-merged-side-wins law, DEC-OPI-32409938…49 R2).
    "0021_provider_usage",
    # veto-response cut (user dogfood first-verification veto): the generic
    # host settings key/value table — this cut writes exactly one key
    # ('rollout_stage', the page-movable tier); W-1-0's world settings reuse
    # the same table in their own follow-up migration (0023).
    "0022_app_settings",
    # W-1-0 (the living-world program's first cut; M0.1
    # DEC-OPI-d96fd92d…7 AD-5): the world's identity binding — the three
    # tables (world / world_actor / world_conversation) the World bounded
    # context's store (elc.world) reads and writes.
    "0023_world_identity",
    # W-1-1 (DEC-OPI-7e3744ee…17): the world's event tree and its minimal
    # state projection — the two tables (world_event / world_state_fact)
    # written only through SqliteWorldStore.record_event's one atomic
    # settlement.
    "0024_world_events",
    # W-1-2 (DEC-OPI-7e3744ee…26): the world run — the one durable row per
    # advance of the living-world engine (deterministic, replayable;
    # M0.1 AD-6: a restart does not re-roll the dice), moved only through
    # SqliteWorldStore's run face.
    "0025_world_runs",
    # W-1-3 (DEC-OPI-7e3744ee…49): the reveal queue — one row per event a
    # run's advance wrote (item_id derived <event_id>:reveal), sitting
    # PENDING until the inbox's atomic reveal_all flips the world's slice to
    # REVEALED; the presentation trigger, never run fuel (spec §4.1).
    "0026_world_reveal",
    # C1-a (DEC-OPI-41a4df20…55): the chronicle attribution foundation —
    # world_event gains participants (the who, strict JSON array) and
    # run_id (the run the event rode, deliberately FK-less); 存量行
    # answer the DEFAULT ('[]' / NULL) with zero back-fill inference.
    "0027_chronicle_attribution",
    # C2 (DEC-OPI-b290799a…45): the storyline cut — the plot layer's
    # own table (world_storyline: theme / opened_by / status /
    # resolve_at; the arcs the narrator's prompt carries and the
    # projection's resolved claims retire from the active read).
    "0028_world_storyline",
    # V3-1 (DEC-OPI-bab4da9f…11/…16): the Narrative V3 foundations —
    # world.current_tick (the story_tick column; the actual tick moves
    # only inside a commit transaction, a later cut's) plus the four
    # tables the Plan/Canon boundary needs: world_chapter /
    # world_chapter_plan / world_scene / world_scene_dossier (the two
    # canon progress rows and the two append-only PLAN rows;
    # elc.world.narrative is their store).
    "0029_narrative_v3_foundations",
    # V3-2 (TASK-OPI-bab4da9f…29): the World Bible — the instance
    # world's sole setting authority as one append-only versioned table
    # (world_bible_revision; the template seeds the first revision at
    # creation and never rewrites an existing world, N-INV-006;
    # elc.world.bible is its store).
    "0030_world_bible",
    # V3-3 (TASK-OPI-bab4da9f…52): the World Cast & Player Identity —
    # the two durable cast faces (world_player_character: the reader's
    # own character, one per world by UNIQUE(world_id);
    # world_actor_profile: each AI actor's narrative profile — story
    # role, POV eligibility/weight, drive, arc seed, private context;
    # elc.world.cast is their store; world_actor untouched).
    "0031_world_cast",
    # V3-3R (TASK-OPI-bab4da9f…61): the identity correction — the
    # external review's item 4: world_actor_profile rebuilt with the
    # composite FK (actor_id, world_id) → world_actor(actor_id,
    # world_id) (the storage invariant; 0023 carries the target
    # UNIQUE; the data face and the CHECK vocabulary unchanged; the
    # store's precheck stays the human-words layer).
    "0032_actor_profile_world_fk",
    # V3-5 (TASK-OPI-be7b094f…34): the SEGMENT COMMIT — the segment's
    # prose (narrative_passage), the decoupled reader-exposure record
    # (reader_exposure) and the V3 story-time lineage row
    # (segment_commit); elc.world.settlement is the commit transaction's
    # face.
    "0033_segment_commit",
    # V3-5R (TASK-OPI-dc1bafdf…13): the terminality correction — the
    # external review's MEDIUM-HIGH: segment_commit gains
    # is_last_segment (the persisted SCENE COMMIT alias fact; one ALTER
    # plus the exact back-fill for the V3-5 pipeline's own product).
    "0034_segment_terminality",
    # V3-6 (TASK-OPI-dc1bafdf…23 / the opening ruling …5, re-run …21):
    # the User Gate and the Action Resolver's durable half — user_gate
    # and user_action (two new tables) plus segment_commit's rebuild
    # ('ACTION_OUTCOME' joins the kind vocabulary, action_id arrives,
    # segment_seq / passage_id go NULLable, is_last_segment and the
    # UNIQUE survive); elc.world.action is the NCP-1 / NCP-2 face.
    "0035_user_gate_action",
    # V3-6R (TASK-OPI-dc1bafdf…33 / the opening ruling …31): the
    # external review's HIGH-1 — action_replan, the durable replan
    # obligation a ruling's replan_scope ≠ NONE leaves behind (the
    # crash-proof anchor between NCP-2's short transaction and the plan
    # face that consumes the verdict; claim → work → complete).
    "0036_action_replan",
)

#: The newest migration's file name, and the ``schema_version`` /
#: ``runtime_schema_version`` stamp that applying the whole chain leaves.
SCHEMA_HEAD_FILE = "0036_action_replan.sql"
SCHEMA_HEAD_VERSION = "36"

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
