"""V3-1 — the Narrative V3 foundations (seven pin groups).

The Narrative V3 paradigm shift's first code cut (DEC-OPI-bab4da9f…11
landed the contract in the four canonical V3 sections,
DEC-OPI-bab4da9f…16 released the migration and the code): migration
0029's one column and four tables, the story_tick primitives
(:mod:`elc.world.time`), and the narrative store's lifecycle faces.
Foundations only — no commit transaction, no passage/gate/action
table, no planning engine (the later cuts' work; nothing here writes
canon). The groups:

1. **tick pins** — a fresh world reads tick 0 (the column's DEFAULT),
   :func:`elc.world.time.advance_current_tick` is monotone (``delta >=
   0`` only, the value never moves backwards), a negative delta is a
   value-semantics ``VALIDATION_FAILED`` refusal and a missing world a
   ``NOT_FOUND`` (STATE_MACHINES §26 / §27; N-INV-007's primitive);
2. **chapter pins** — the four-word machine ``PLANNED → ACTIVE →
   SETTLING → CLOSED`` walks legally, every illegal move (including
   ``CLOSED → ACTIVE``, §27's list) is refused ``VALIDATION_FAILED``,
   and a world holds **at most one ACTIVE chapter** (the second is
   refused until the first closes);
3. **scene pins** — the five-word machine walks legally
   (``PLANNED → ACTIVE → COMMITTED → CLOSED`` plus ``PLANNED →
   DISCARDED``), ``DISCARDED`` is reachable **only from PLANNED**
   (an ACTIVE scene's flip is refused, a COMMITTED scene's doubly so —
   §22's rule / §27's 「有已 commit 段落的 scene → DISCARDED」), a
   committed scene cannot regress, and the actual tick columns stay
   ``None`` (the actual span is the commits' — the later cuts' write
   face);
4. **plan / dossier pins** — the Plan face is append-only versioned
   (revisions never rewrite; a same-(chapter, revision) different-id
   clash is a ``CONFLICT``), ``ADOPTED`` is unique per planned row
   (adopting the new revision supersedes the old in one transaction),
   ``REJECTED`` records a veto, and only a ``PROPOSED`` revision
   adopts (history never adopts again);
5. **Plan↔Canon isolation pins** — the source-level scan (the Gate-2
   precedent's AST手法): the canon read methods' SQL never names
   ``world_chapter_plan`` / ``world_scene_dossier`` (N-INV-001 /
   N-R-INV-007 — uncommitted Plan content is never readable as fact),
   the plan-face reads mirror the same isolation the other way, and
   the record markers keep the two faces apart at the type level;
6. **V2-chain pins** — the legacy Narrative V2 surfaces
   (``world_run`` / ``world_reveal_item`` / ``world_event``) are
   untouched by every V3 write (row counts stay put through a full V3
   lifecycle), and the world store's own methods behave unchanged
   alongside the V3 activity (N-R-INV-008's two-chains law);
7. **migration self-pin** — the shared constants say
   ``0029_narrative_v3_foundations`` / ``29``, a fresh database stamps
   exactly that, and the live schema carries the contract's shape
   (columns, CHECK vocabularies, UNIQUE keys, FKs — read off the
   migrated database through PRAGMA and ``sqlite_master``).
"""

from __future__ import annotations

import ast
import re
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from elc.platform.db.epoch import open_runtime_epoch
from elc.platform.db.migrations import apply_migrations, schema_version
from elc.platform.types import (
    DomainErrorCode,
    Err,
    Ok,
    Result,
)
from elc.world.narrative import (
    CanonProgressRecord,
    PlanFaceRecord,
    PlanRevisionStatus,
    SqliteNarrativeStore,
    WorldChapterPlanRecord,
    WorldChapterRecord,
    WorldSceneDossierRecord,
    WorldSceneRecord,
)
from elc.world.store import SqliteWorldStore
from elc.world.time import advance_current_tick, read_current_tick
from elc.world.types import StateEffect, WorldEvent
from tests.conftest import (
    MIGRATION_IDS,
    SCHEMA_HEAD_FILE,
    SCHEMA_HEAD_VERSION,
    SRC_ROOT,
)

REPO = Path(__file__).resolve().parents[2]

NOW = "2026-10-12T00:00:00+00:00"
LATER = "2026-10-12T01:00:00+00:00"


# ---------------------------------------------------------------------------
# shared fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    """A fresh, fully migrated app.db — the production profile's
    foreign-keys-ON (the dangling-reference refusals are the database's
    own, so the fixture must spell the same posture
    ``elc.platform.db.connection.connect`` does)."""

    db = sqlite3.connect(tmp_path / "app.db")
    db.execute("PRAGMA foreign_keys=ON")
    apply_migrations(db)
    return db


@pytest.fixture()
def store(conn: sqlite3.Connection) -> SqliteNarrativeStore:
    """The narrative store over the fresh database."""

    fence = open_runtime_epoch(conn)
    return SqliteNarrativeStore(conn, fence)


@pytest.fixture()
def world_store(conn: sqlite3.Connection) -> SqliteWorldStore:
    """The legacy world store over the same database — the V2 chain's
    face and the world-row maker the FK targets need."""

    fence = open_runtime_epoch(conn)
    return SqliteWorldStore(conn, fence)


def _seed_world(
    world_store: SqliteWorldStore, world_id: str = "world-main"
) -> None:
    result = world_store.create_world(world_id, "Berrymoor", None, NOW)
    assert isinstance(result, Ok)


def _seed_chapter(
    store: SqliteNarrativeStore,
    chapter_id: str = "chapter-main-1",
    world_id: str = "world-main",
    chapter_index: int = 1,
) -> WorldChapterRecord:
    result = store.create_chapter(chapter_id, world_id, chapter_index, NOW)
    assert isinstance(result, Ok)
    assert result.value is not None
    return result.value


def _seed_scene(
    store: SqliteNarrativeStore,
    scene_id: str = "scene-main-1-1",
    chapter_id: str = "chapter-main-1",
    scene_index: int = 1,
) -> WorldSceneRecord:
    result = store.create_scene(scene_id, chapter_id, scene_index, NOW)
    assert isinstance(result, Ok)
    assert result.value is not None
    return result.value


def _plan_kwargs() -> dict[str, Any]:
    """One Blueprint-shaped payload — the soft-expectation set is the
    V3-0R wording law's own fields, never a postcondition."""

    return {
        "goal": "Lia and the user truly meet",
        "dramatic_question": "Will the estate's secret surface?",
        "planned_start_tick": 0,
        "planned_end_tick": 600,
        "closing_pressure": "the estate's silence presses in",
        "desired_development": "trust grows by inches",
        "soft_outcomes": "an alliance, maybe",
        "chapter_questions_to_advance": "who forged the letter?",
        "scenes": (
            {
                "purpose": "first sight",
                "planned_start_tick": 0,
                "place": "the manor steps",
                "pov": "actor-lia",
            },
        ),
    }


def _create_plan(
    store: SqliteNarrativeStore,
    chapter_id: str = "chapter-main-1",
    plan_revision: int = 1,
    chapter_plan_id: str = "plan-main-1-r1",
    **overrides: Any,
) -> Result[WorldChapterPlanRecord]:
    kwargs = _plan_kwargs() | overrides
    return store.create_plan(
        chapter_plan_id, chapter_id, plan_revision, now=NOW, **kwargs
    )


def _dossier_kwargs() -> dict[str, Any]:
    """One Dossier-shaped payload — the POV discipline's own fields."""

    return {
        "pov_actor_id": "actor-lia",
        "participants": ("actor-lia", "player-character-1"),
        "place": "the manor steps",
        "planned_start_tick": 10,
        "revealable": "the letter's seal",
        "must_hide": "the father's coup",
        "entry_goals": "lia: greet the newcomer",
        "exit_condition": "the greeting lands or breaks",
        "elasticity": "may run long if the user lingers",
    }


def _create_dossier(
    store: SqliteNarrativeStore,
    scene_id: str = "scene-main-1-1",
    dossier_revision: int = 1,
    dossier_id: str = "dossier-main-1-1-r1",
    **overrides: Any,
) -> Result[WorldSceneDossierRecord]:
    kwargs = _dossier_kwargs() | overrides
    return store.create_dossier(
        dossier_id, scene_id, dossier_revision, now=NOW, **kwargs
    )


# ---------------------------------------------------------------------------
# 1. tick pins
# ---------------------------------------------------------------------------


def test_a_fresh_world_reads_tick_zero(
    conn: sqlite3.Connection, world_store: SqliteWorldStore
) -> None:
    _seed_world(world_store)
    result = read_current_tick(conn, "world-main")
    assert isinstance(result, Ok)
    assert result.value == 0


def test_advance_is_monotone_and_zero_is_legal(
    conn: sqlite3.Connection, world_store: SqliteWorldStore
) -> None:
    _seed_world(world_store)
    first = advance_current_tick(conn, "world-main", 5)
    assert isinstance(first, Ok)
    assert first.value == 5
    zero = advance_current_tick(conn, "world-main", 0)
    assert isinstance(zero, Ok)
    assert zero.value == 5
    second = advance_current_tick(conn, "world-main", 3)
    assert isinstance(second, Ok)
    assert second.value == 8
    again = read_current_tick(conn, "world-main")
    assert isinstance(again, Ok)
    assert again.value == 8


def test_a_negative_delta_is_refused_and_the_tick_does_not_move(
    conn: sqlite3.Connection, world_store: SqliteWorldStore
) -> None:
    _seed_world(world_store)
    assert isinstance(advance_current_tick(conn, "world-main", 7), Ok)
    refused = advance_current_tick(conn, "world-main", -1)
    assert isinstance(refused, Err)
    assert refused.error.code == DomainErrorCode.VALIDATION_FAILED
    unchanged = read_current_tick(conn, "world-main")
    assert isinstance(unchanged, Ok)
    assert unchanged.value == 7


def test_tick_of_a_missing_world_is_not_found(conn: sqlite3.Connection) -> None:
    read_miss = read_current_tick(conn, "world-nowhere")
    assert isinstance(read_miss, Err)
    assert read_miss.error.code == DomainErrorCode.NOT_FOUND
    advance_miss = advance_current_tick(conn, "world-nowhere", 5)
    assert isinstance(advance_miss, Err)
    assert advance_miss.error.code == DomainErrorCode.NOT_FOUND


# ---------------------------------------------------------------------------
# 2. chapter pins
# ---------------------------------------------------------------------------


def test_chapter_mints_planned_and_replays_idempotently(
    store: SqliteNarrativeStore, world_store: SqliteWorldStore
) -> None:
    _seed_world(world_store)
    created = _seed_chapter(store)
    assert created.status.value == "PLANNED"
    assert created.state_version == 1
    assert created.opened_at_tick is None
    assert created.closed_at_tick is None
    replay = store.create_chapter("chapter-main-1", "world-main", 1, LATER)
    assert isinstance(replay, Ok)
    assert replay.value is not None
    assert replay.value.status.value == "PLANNED"
    different = store.create_chapter("chapter-main-1", "world-main", 2, NOW)
    assert isinstance(different, Err)
    assert different.error.code == DomainErrorCode.CONFLICT


def test_chapter_walks_the_full_legal_path(
    store: SqliteNarrativeStore, world_store: SqliteWorldStore
) -> None:
    _seed_world(world_store)
    chapter = _seed_chapter(store)
    opened = store.activate_chapter(
        chapter.chapter_id, opened_at_tick=0, now=NOW, expected_state_version=1
    )
    assert isinstance(opened, Ok)
    assert opened.value is not None
    assert opened.value.status.value == "ACTIVE"
    assert opened.value.opened_at_tick == 0
    assert opened.value.state_version == 2
    settled = store.settle_chapter(
        chapter.chapter_id, now=LATER, expected_state_version=2
    )
    assert isinstance(settled, Ok)
    assert settled.value is not None
    assert settled.value.status.value == "SETTLING"
    closed = store.close_chapter(
        chapter.chapter_id,
        closed_at_tick=90,
        now=LATER,
        expected_state_version=3,
    )
    assert isinstance(closed, Ok)
    assert closed.value is not None
    assert closed.value.status.value == "CLOSED"
    assert closed.value.closed_at_tick == 90
    ordered = store.chapters_of("world-main")
    assert [row.chapter_index for row in ordered] == [1]
    assert store.active_chapter("world-main") is None


def test_chapter_illegal_moves_are_refused(
    store: SqliteNarrativeStore, world_store: SqliteWorldStore
) -> None:
    _seed_world(world_store)
    chapter = _seed_chapter(store)
    # SETTLING from PLANNED — the machine's order is not negotiable.
    early = store.settle_chapter(
        chapter.chapter_id, now=NOW, expected_state_version=1
    )
    assert isinstance(early, Err)
    assert early.error.code == DomainErrorCode.VALIDATION_FAILED
    # CLOSED from ACTIVE — the settlement runs first.
    opened = store.activate_chapter(
        chapter.chapter_id, opened_at_tick=0, now=NOW, expected_state_version=1
    )
    assert isinstance(opened, Ok)
    jumped = store.close_chapter(
        chapter.chapter_id, closed_at_tick=5, now=NOW, expected_state_version=2
    )
    assert isinstance(jumped, Err)
    assert jumped.error.code == DomainErrorCode.VALIDATION_FAILED
    settled = store.settle_chapter(
        chapter.chapter_id, now=NOW, expected_state_version=2
    )
    assert isinstance(settled, Ok)
    closed = store.close_chapter(
        chapter.chapter_id, closed_at_tick=5, now=NOW, expected_state_version=3
    )
    assert isinstance(closed, Ok)
    # CLOSED → ACTIVE — §27's list, word for word.
    reopened = store.activate_chapter(
        chapter.chapter_id, opened_at_tick=5, now=NOW, expected_state_version=4
    )
    assert isinstance(reopened, Err)
    assert reopened.error.code == DomainErrorCode.VALIDATION_FAILED
    assert "CLOSED" in (reopened.error.message or "")


def test_a_world_holds_at_most_one_active_chapter(
    store: SqliteNarrativeStore, world_store: SqliteWorldStore
) -> None:
    _seed_world(world_store)
    first = _seed_chapter(store, "chapter-main-1", chapter_index=1)
    second = _seed_chapter(store, "chapter-main-2", chapter_index=2)
    assert isinstance(
        store.activate_chapter(first.chapter_id, 0, NOW, expected_state_version=1),
        Ok,
    )
    second_try = store.activate_chapter(
        second.chapter_id, 0, NOW, expected_state_version=1
    )
    assert isinstance(second_try, Err)
    assert second_try.error.code == DomainErrorCode.VALIDATION_FAILED
    assert "one chapter at a time" in (second_try.error.message or "")
    # The refusal released nothing: the first chapter is still the one.
    active = store.active_chapter("world-main")
    assert active is not None
    assert active.chapter_id == "chapter-main-1"
    # Once the first closes, the second may open (the chapters walk on).
    assert isinstance(
        store.settle_chapter(first.chapter_id, NOW, expected_state_version=2), Ok
    )
    assert isinstance(
        store.close_chapter(first.chapter_id, 90, NOW, expected_state_version=3),
        Ok,
    )
    assert isinstance(
        store.activate_chapter(second.chapter_id, 90, NOW, expected_state_version=1),
        Ok,
    )


def test_chapter_refusals_are_value_semantics(
    store: SqliteNarrativeStore, world_store: SqliteWorldStore
) -> None:
    _seed_world(world_store)
    dangling = store.create_chapter("chapter-x", "world-nowhere", 1, NOW)
    assert isinstance(dangling, Err)
    assert dangling.error.code == DomainErrorCode.NOT_FOUND
    _seed_chapter(store, "chapter-main-1", chapter_index=1)
    clash = store.create_chapter("chapter-other", "world-main", 1, NOW)
    assert isinstance(clash, Err)
    assert clash.error.code == DomainErrorCode.CONFLICT
    # The CAS guard: a stale expected version is a CONFLICT, the row
    # answers where it stands.
    stale = store.activate_chapter(
        "chapter-main-1", 0, NOW, expected_state_version=99
    )
    assert isinstance(stale, Err)
    assert stale.error.code == DomainErrorCode.CONFLICT
    missing = store.activate_chapter(
        "chapter-ghost", 0, NOW, expected_state_version=1
    )
    assert isinstance(missing, Err)
    assert missing.error.code == DomainErrorCode.NOT_FOUND


# ---------------------------------------------------------------------------
# 3. scene pins
# ---------------------------------------------------------------------------


def test_scene_mints_planned_and_the_actual_span_stays_empty(
    store: SqliteNarrativeStore, world_store: SqliteWorldStore
) -> None:
    _seed_world(world_store)
    _seed_chapter(store)
    scene = _seed_scene(store)
    assert scene.status.value == "PLANNED"
    assert scene.actual_start_tick is None
    assert scene.actual_end_tick is None
    replay = store.create_scene("scene-main-1-1", "chapter-main-1", 1, LATER)
    assert isinstance(replay, Ok)


def test_scene_walks_the_full_legal_path(
    store: SqliteNarrativeStore, world_store: SqliteWorldStore
) -> None:
    _seed_world(world_store)
    _seed_chapter(store)
    scene = _seed_scene(store)
    activated = store.activate_scene(scene.scene_id, now=NOW, expected_state_version=1)
    assert isinstance(activated, Ok)
    assert activated.value is not None
    assert activated.value.status.value == "ACTIVE"
    # The actual span is the commits' — activation stamps nothing.
    assert activated.value.actual_start_tick is None
    committed = store.commit_scene(scene.scene_id, now=NOW, expected_state_version=2)
    assert isinstance(committed, Ok)
    assert committed.value is not None
    assert committed.value.status.value == "COMMITTED"
    closed = store.close_scene(scene.scene_id, now=NOW, expected_state_version=3)
    assert isinstance(closed, Ok)
    assert closed.value is not None
    assert closed.value.status.value == "CLOSED"
    assert [row.scene_index for row in store.scenes_of("chapter-main-1")] == [1]


def test_discarded_is_reachable_only_from_planned(
    store: SqliteNarrativeStore, world_store: SqliteWorldStore
) -> None:
    _seed_world(world_store)
    _seed_chapter(store)
    planned = _seed_scene(store, "scene-planned", scene_index=1)
    discarded = store.discard_scene(
        planned.scene_id, now=NOW, expected_state_version=1
    )
    assert isinstance(discarded, Ok)
    assert discarded.value is not None
    assert discarded.value.status.value == "DISCARDED"
    # An ACTIVE scene has the Dossier's writing under way — not discardable.
    active = _seed_scene(store, "scene-active", scene_index=2)
    assert isinstance(store.activate_scene(active.scene_id, NOW, 1), Ok)
    active_refused = store.discard_scene(
        active.scene_id, now=NOW, expected_state_version=2
    )
    assert isinstance(active_refused, Err)
    assert active_refused.error.code == DomainErrorCode.VALIDATION_FAILED
    # A COMMITTED scene has canon on the ground — §27's word, refused.
    assert isinstance(store.commit_scene(active.scene_id, NOW, 2), Ok)
    committed_refused = store.discard_scene(
        active.scene_id, now=NOW, expected_state_version=3
    )
    assert isinstance(committed_refused, Err)
    assert committed_refused.error.code == DomainErrorCode.VALIDATION_FAILED
    # An already-discarded scene is history — nothing moves it again.
    again = store.discard_scene(planned.scene_id, now=NOW, expected_state_version=2)
    assert isinstance(again, Err)
    assert again.error.code == DomainErrorCode.VALIDATION_FAILED


def test_a_committed_scene_cannot_regress(
    store: SqliteNarrativeStore, world_store: SqliteWorldStore
) -> None:
    _seed_world(world_store)
    _seed_chapter(store)
    scene = _seed_scene(store)
    assert isinstance(store.activate_scene(scene.scene_id, NOW, 1), Ok)
    assert isinstance(store.commit_scene(scene.scene_id, NOW, 2), Ok)
    back_to_active = store.activate_scene(
        scene.scene_id, now=NOW, expected_state_version=3
    )
    assert isinstance(back_to_active, Err)
    assert back_to_active.error.code == DomainErrorCode.VALIDATION_FAILED
    commit_again = store.commit_scene(scene.scene_id, now=NOW, expected_state_version=3)
    assert isinstance(commit_again, Err)
    assert commit_again.error.code == DomainErrorCode.VALIDATION_FAILED
    # CLOSED is terminal in this machine too (§27: no re-ACTIVE).
    assert isinstance(store.close_scene(scene.scene_id, NOW, 3), Ok)
    reopened = store.activate_scene(scene.scene_id, NOW, 4)
    assert isinstance(reopened, Err)
    assert reopened.error.code == DomainErrorCode.VALIDATION_FAILED


def test_scene_illegal_jumps_are_refused(
    store: SqliteNarrativeStore, world_store: SqliteWorldStore
) -> None:
    _seed_world(world_store)
    _seed_chapter(store)
    scene = _seed_scene(store)
    # PLANNED → COMMITTED and PLANNED → CLOSED: the machine's order only.
    early_commit = store.commit_scene(scene.scene_id, now=NOW, expected_state_version=1)
    assert isinstance(early_commit, Err)
    assert early_commit.error.code == DomainErrorCode.VALIDATION_FAILED
    early_close = store.close_scene(scene.scene_id, now=NOW, expected_state_version=1)
    assert isinstance(early_close, Err)
    assert early_close.error.code == DomainErrorCode.VALIDATION_FAILED
    dangling = store.create_scene("scene-x", "chapter-ghost", 1, NOW)
    assert isinstance(dangling, Err)
    assert dangling.error.code == DomainErrorCode.NOT_FOUND
    _seed_scene(store, "scene-two", scene_index=2)
    clash = store.create_scene("scene-other", "chapter-main-1", 2, NOW)
    assert isinstance(clash, Err)
    assert clash.error.code == DomainErrorCode.CONFLICT


# ---------------------------------------------------------------------------
# 4. plan / dossier pins
# ---------------------------------------------------------------------------


def test_plan_mints_proposed_and_replays_idempotently(
    store: SqliteNarrativeStore, world_store: SqliteWorldStore
) -> None:
    _seed_world(world_store)
    _seed_chapter(store)
    created = _create_plan(store)
    assert isinstance(created, Ok)
    assert created.value is not None
    assert created.value.status == PlanRevisionStatus.PROPOSED
    assert created.value.state_version == 1
    replay = _create_plan(store)
    assert isinstance(replay, Ok)
    assert replay.value is not None
    assert replay.value.status == PlanRevisionStatus.PROPOSED
    different = _create_plan(store, goal="a different goal")
    assert isinstance(different, Err)
    assert different.error.code == DomainErrorCode.CONFLICT


def test_plan_adoptions_supersede_and_adopted_is_unique(
    store: SqliteNarrativeStore, world_store: SqliteWorldStore
) -> None:
    _seed_world(world_store)
    _seed_chapter(store)
    first = _create_plan(store, plan_revision=1, chapter_plan_id="plan-r1")
    second = _create_plan(store, plan_revision=2, chapter_plan_id="plan-r2")
    assert isinstance(first, Ok)
    assert isinstance(second, Ok)
    adopted = store.adopt_plan("plan-r1", now=NOW, expected_state_version=1)
    assert isinstance(adopted, Ok)
    assert adopted.value is not None
    assert adopted.value.status == PlanRevisionStatus.ADOPTED
    current = store.adopted_plan("chapter-main-1")
    assert current is not None
    assert current.chapter_plan_id == "plan-r1"
    # Adopting the newer revision supersedes the old, in one transaction.
    adopted_two = store.adopt_plan("plan-r2", now=NOW, expected_state_version=1)
    assert isinstance(adopted_two, Ok)
    superseded = store.get_plan("plan-r1")
    assert superseded is not None
    assert superseded.status == PlanRevisionStatus.SUPERSEDED
    assert superseded.state_version == 3  # 1 mint, 2 adopt, 3 supersede
    current = store.adopted_plan("chapter-main-1")
    assert current is not None
    assert current.chapter_plan_id == "plan-r2"
    # History never adopts again (only PROPOSED adopts).
    again = store.adopt_plan("plan-r1", now=NOW, expected_state_version=2)
    assert isinstance(again, Err)
    assert again.error.code == DomainErrorCode.VALIDATION_FAILED


def test_plan_rejection_records_the_veto(
    store: SqliteNarrativeStore, world_store: SqliteWorldStore
) -> None:
    _seed_world(world_store)
    _seed_chapter(store)
    assert isinstance(_create_plan(store), Ok)
    rejected = store.reject_plan(
        "plan-main-1-r1", now=NOW, expected_state_version=1
    )
    assert isinstance(rejected, Ok)
    assert rejected.value is not None
    assert rejected.value.status == PlanRevisionStatus.REJECTED
    # A rejected revision is history: it neither adopts nor rejects twice.
    adopt_refused = store.adopt_plan("plan-main-1-r1", NOW, 2)
    assert isinstance(adopt_refused, Err)
    assert adopt_refused.error.code == DomainErrorCode.VALIDATION_FAILED
    twice = store.reject_plan("plan-main-1-r1", NOW, 2)
    assert isinstance(twice, Err)
    assert twice.error.code == DomainErrorCode.VALIDATION_FAILED
    assert store.adopted_plan("chapter-main-1") is None


def test_plan_shapes_and_dangling_refs_are_refused(
    store: SqliteNarrativeStore, world_store: SqliteWorldStore
) -> None:
    _seed_world(world_store)
    _seed_chapter(store)
    assert isinstance(_create_plan(store), Ok)
    # Another revision id under the same (chapter, plan_revision) UNIQUE.
    clash = _create_plan(store, chapter_plan_id="plan-other")
    assert isinstance(clash, Err)
    assert clash.error.code == DomainErrorCode.CONFLICT
    dangling = _create_plan(
        store, chapter_id="chapter-ghost", chapter_plan_id="plan-ghost"
    )
    assert isinstance(dangling, Err)
    assert dangling.error.code == DomainErrorCode.NOT_FOUND
    stale = store.reject_plan("plan-main-1-r1", NOW, 99)
    assert isinstance(stale, Err)
    assert stale.error.code == DomainErrorCode.CONFLICT
    assert [plan.plan_revision for plan in store.plans_of("chapter-main-1")] == [1]


def test_dossier_walks_the_same_append_only_law(
    store: SqliteNarrativeStore, world_store: SqliteWorldStore
) -> None:
    _seed_world(world_store)
    _seed_chapter(store)
    _seed_scene(store)
    created = _create_dossier(store)
    assert isinstance(created, Ok)
    assert created.value is not None
    assert created.value.status == PlanRevisionStatus.PROPOSED
    assert created.value.participants == ("actor-lia", "player-character-1")
    revision_two = _create_dossier(
        store, dossier_revision=2, dossier_id="dossier-r2"
    )
    assert isinstance(revision_two, Ok)
    assert isinstance(store.adopt_dossier("dossier-main-1-1-r1", NOW, 1), Ok)
    assert isinstance(store.adopt_dossier("dossier-r2", NOW, 1), Ok)
    superseded = store.get_dossier("dossier-main-1-1-r1")
    assert superseded is not None
    assert superseded.status == PlanRevisionStatus.SUPERSEDED
    current = store.adopted_dossier("scene-main-1-1")
    assert current is not None
    assert current.dossier_id == "dossier-r2"
    assert [
        row.dossier_revision for row in store.dossiers_of("scene-main-1-1")
    ] == [1, 2]
    rejected_third = _create_dossier(
        store, dossier_revision=3, dossier_id="dossier-r3"
    )
    assert isinstance(rejected_third, Ok)
    assert isinstance(store.reject_dossier("dossier-r3", NOW, 1), Ok)
    adopt_refused = store.adopt_dossier("dossier-r3", NOW, 2)
    assert isinstance(adopt_refused, Err)
    assert adopt_refused.error.code == DomainErrorCode.VALIDATION_FAILED
    dangling = _create_dossier(
        store, scene_id="scene-ghost", dossier_id="dossier-ghost"
    )
    assert isinstance(dangling, Err)
    assert dangling.error.code == DomainErrorCode.NOT_FOUND


# ---------------------------------------------------------------------------
# 5. Plan↔Canon isolation pins (the Gate-2 precedent's AST手法)
# ---------------------------------------------------------------------------

_STORE_SOURCE = (SRC_ROOT / "world" / "narrative" / "store.py").read_text(
    encoding="utf-8"
)
_STORE_TREE = ast.parse(_STORE_SOURCE, filename="store.py")

_CANON_READS = (
    "get_chapter",
    "chapters_of",
    "active_chapter",
    "get_scene",
    "scenes_of",
)
_PLAN_READS = (
    "get_plan",
    "plans_of",
    "adopted_plan",
    "get_dossier",
    "dossiers_of",
    "adopted_dossier",
)


def _sql_strings_of(method_name: str) -> list[str]:
    """The SQL strings one method carries — string constants that smell
    like SQL (the docstrings ride other constants and are skipped, so a
    prose mention of a table name cannot false-positive)."""

    for node in ast.walk(_STORE_TREE):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
            node.name == method_name
        ):
            found: list[str] = []
            for child in ast.walk(node):
                if isinstance(child, ast.Constant) and isinstance(
                    child.value, str
                ):
                    text = child.value
                    if re.search(r"\b(select|update|insert)\b", text, re.IGNORECASE):
                        found.append(text)
            return found
    raise AssertionError(f"method {method_name!r} not found in the store source")


def test_canon_read_sql_never_names_the_plan_tables() -> None:
    """N-INV-001 / N-R-INV-007 at the source level: the canon read face
    (the progress rows a reader treats as fact) never touches
    ``world_chapter_plan`` / ``world_scene_dossier`` — uncommitted Plan
    content is structurally unreachable from these queries, not merely
    undocumented."""

    offenders: list[str] = []
    for method in _CANON_READS:
        for sql in _sql_strings_of(method):
            if "world_chapter_plan" in sql or "world_scene_dossier" in sql:
                offenders.append(f"{method}: {sql!r}")
    assert not offenders, f"canon reads touch the Plan face: {offenders}"


def test_plan_read_sql_never_names_the_canon_progress_tables() -> None:
    """The mirror isolation: the Plan face's reads never query
    ``world_chapter`` / ``world_scene`` either (the word-boundary
    negative lookahead keeps ``world_chapter_plan`` itself legal — the
    plan tables are the Plan face's own)."""

    offenders: list[str] = []
    for method in _PLAN_READS:
        for sql in _sql_strings_of(method):
            if re.search(r"world_chapter(?!_plan)", sql) or re.search(
                r"world_scene(?!_dossier)", sql
            ):
                offenders.append(f"{method}: {sql!r}")
    assert not offenders, f"plan reads touch the canon face: {offenders}"


def test_the_two_record_faces_share_no_marker_base() -> None:
    """The Plan/Canon boundary is a type distinction: the plan records
    are :class:`PlanFaceRecord` and never :class:`CanonProgressRecord`
    (and the other way) — a type confusion between the faces is a bug
    the type system can see."""

    assert issubclass(WorldChapterRecord, CanonProgressRecord)
    assert issubclass(WorldSceneRecord, CanonProgressRecord)
    assert not issubclass(WorldChapterRecord, PlanFaceRecord)
    assert not issubclass(WorldSceneRecord, PlanFaceRecord)
    assert issubclass(WorldChapterPlanRecord, PlanFaceRecord)
    assert issubclass(WorldSceneDossierRecord, PlanFaceRecord)
    assert not issubclass(WorldChapterPlanRecord, CanonProgressRecord)
    assert not issubclass(WorldSceneDossierRecord, CanonProgressRecord)


def test_plan_content_never_leaks_into_canon_reads(
    store: SqliteNarrativeStore, world_store: SqliteWorldStore
) -> None:
    """The behavioral face of the same boundary: a world carrying an
    adopted Blueprint and an adopted Dossier still reads as zero canon
    progress — the plan rows are the only rows the plans produced."""

    _seed_world(world_store)
    _seed_chapter(store)
    _seed_scene(store)
    assert isinstance(_create_plan(store), Ok)
    assert isinstance(store.adopt_plan("plan-main-1-r1", NOW, 1), Ok)
    assert isinstance(_create_dossier(store), Ok)
    assert isinstance(store.adopt_dossier("dossier-main-1-1-r1", NOW, 1), Ok)
    chapters = store.chapters_of("world-main")
    assert len(chapters) == 1
    assert chapters[0].status.value == "PLANNED"
    assert store.active_chapter("world-main") is None
    scenes = store.scenes_of("chapter-main-1")
    assert len(scenes) == 1
    assert scenes[0].status.value == "PLANNED"
    assert scenes[0].actual_start_tick is None


# ---------------------------------------------------------------------------
# 6. V2-chain pins (N-R-INV-008)
# ---------------------------------------------------------------------------


def test_v3_writes_leave_the_legacy_surfaces_untouched(
    conn: sqlite3.Connection,
    store: SqliteNarrativeStore,
    world_store: SqliteWorldStore,
) -> None:
    """A full V3 lifecycle (chapter + scene + plan + dossier + tick)
    writes nothing into ``world_run`` / ``world_reveal_item`` /
    ``world_event`` — the legacy chain's rows are the V2 chain's alone,
    and the V2 store reads back exactly what it wrote."""

    _seed_world(world_store)
    event = world_store.record_event(
        WorldEvent(
            event_id="event-v2-1",
            world_id="world-main",
            kind="beat",
            narration="the morning bell",
            effects=(StateEffect(key="mood", statement="the estate wakes"),),
            occurred_at=NOW,
            source="test",
        )
    )
    assert isinstance(event, Ok)
    counts_before = {
        table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("world_run", "world_reveal_item", "world_event")
    }
    assert counts_before == {
        "world_run": 0,
        "world_reveal_item": 0,
        "world_event": 1,
    }

    _seed_chapter(store)
    _seed_scene(store)
    assert isinstance(_create_plan(store), Ok)
    assert isinstance(store.adopt_plan("plan-main-1-r1", NOW, 1), Ok)
    assert isinstance(_create_dossier(store), Ok)
    assert isinstance(store.adopt_dossier("dossier-main-1-1-r1", NOW, 1), Ok)
    assert isinstance(store.activate_chapter("chapter-main-1", 0, NOW, 1), Ok)
    assert isinstance(advance_current_tick(conn, "world-main", 15), Ok)
    # The tick primitive owns no transaction (the commit transaction's
    # composability) — this test is the caller here, so it commits the
    # way every raw-DML caller does.
    conn.commit()

    counts_after = {
        table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("world_run", "world_reveal_item", "world_event")
    }
    assert counts_after == counts_before
    chronicle = world_store.chronicle_of("world-main")
    assert isinstance(chronicle, Ok)
    assert chronicle.value is not None
    assert [row.event_id for row in chronicle.value] == ["event-v2-1"]
    # The V2 store's own writes still land alongside the V3 activity.
    followup = world_store.record_event(
        WorldEvent(
            event_id="event-v2-2",
            world_id="world-main",
            kind="beat",
            narration="the gate opens",
            effects=(),
            occurred_at=LATER,
            source="test",
        )
    )
    assert isinstance(followup, Ok)
    assert conn.execute("SELECT COUNT(*) FROM world_event").fetchone()[0] == 2


# ---------------------------------------------------------------------------
# 7. migration self-pin
# ---------------------------------------------------------------------------


def test_the_shared_constants_and_a_fresh_db_say_the_chain_head() -> None:
    # The head literal moves with each head (the P9-1 way): this pin
    # read 0029's own names while 0029 was the head; V3-2's
    # 0030_world_bible moved them again — the migration-shape claims in
    # the sibling tests stay 0029's own.
    assert MIGRATION_IDS[-1] == "0030_world_bible"
    assert SCHEMA_HEAD_FILE == "0030_world_bible.sql"
    assert SCHEMA_HEAD_VERSION == "30"
    fresh = sqlite3.connect(":memory:")
    applied = apply_migrations(fresh)
    assert applied[-1] == "0030_world_bible"
    assert schema_version(fresh) == SCHEMA_HEAD_VERSION == "30"
    stamps = dict(
        fresh.execute(
            "SELECT key, value FROM schema_meta"
            " WHERE key LIKE '%schema_version%'"
        ).fetchall()
    )
    assert stamps == {
        "schema_version": "30",
        "runtime_schema_version": "30",
    }


def test_the_fresh_world_column_and_the_four_tables_exist(
    conn: sqlite3.Connection,
) -> None:
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    assert {
        "world_chapter",
        "world_chapter_plan",
        "world_scene",
        "world_scene_dossier",
    } <= tables
    columns = [
        row[1] for row in conn.execute("PRAGMA table_info(world)").fetchall()
    ]
    assert "current_tick" in columns
    default_row = conn.execute(
        "SELECT dflt_value FROM pragma_table_info('world')"
        " WHERE name = 'current_tick'"
    ).fetchone()
    assert default_row is not None
    assert str(default_row[0]) == "0"


def test_the_four_tables_carry_the_contract_shape(
    conn: sqlite3.Connection,
) -> None:
    """The migration's own spelling, read off the live schema: the
    CHECK vocabularies are the canonical word lists word for word, the
    UNIQUE keys are the idempotency key set (DATA §26.2.4), and the
    FKs chain the plan face to the canon progress rows."""

    sql_of = {
        row[0]: str(row[1])
        for row in conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type = 'table'"
            " AND name IN ('world_chapter', 'world_chapter_plan',"
            " 'world_scene', 'world_scene_dossier')"
        ).fetchall()
    }
    assert (
        "CHECK (status IN ('PLANNED','ACTIVE','SETTLING','CLOSED'))"
        in sql_of["world_chapter"]
    )
    assert (
        "CHECK (status IN ('PROPOSED','ADOPTED','SUPERSEDED','REJECTED'))"
        in sql_of["world_chapter_plan"]
    )
    assert (
        "CHECK (status IN ('PLANNED','ACTIVE','COMMITTED','CLOSED','DISCARDED'))"
        in sql_of["world_scene"]
    )
    assert (
        "CHECK (status IN ('PROPOSED','ADOPTED','SUPERSEDED','REJECTED'))"
        in sql_of["world_scene_dossier"]
    )
    for table in sql_of.values():
        assert "CHECK (state_version > 0)" in table
        assert "REFERENCES" in table

    def _unique_columns(table: str) -> list[list[str]]:
        found: list[list[str]] = []
        for index in conn.execute(f"PRAGMA index_list({table})").fetchall():
            if index[2]:  # a UNIQUE index
                found.append(
                    [
                        str(row[2])
                        for row in conn.execute(
                            f"PRAGMA index_info({index[1]})"
                        ).fetchall()
                    ]
                )
        return found

    assert ["world_id", "chapter_index"] in _unique_columns("world_chapter")
    assert ["chapter_id", "plan_revision"] in _unique_columns("world_chapter_plan")
    assert ["chapter_id", "scene_index"] in _unique_columns("world_scene")
    assert ["scene_id", "dossier_revision"] in _unique_columns("world_scene_dossier")

    def _fk_targets(table: str) -> dict[str, str]:
        return {
            str(row[3]): str(row[2])
            for row in conn.execute(f"PRAGMA foreign_key_list({table})")
        }

    assert _fk_targets("world_chapter") == {"world_id": "world"}
    assert _fk_targets("world_chapter_plan") == {"chapter_id": "world_chapter"}
    assert _fk_targets("world_scene") == {"chapter_id": "world_chapter"}
    assert _fk_targets("world_scene_dossier") == {"scene_id": "world_scene"}
