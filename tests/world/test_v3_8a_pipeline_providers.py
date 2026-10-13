"""V3-8a — the atomic creation service, the provider protocol face and
the V3 pipeline orchestrator (TASK-OPI-06b954e0…4 / the opening ruling
``DEC-OPI-06b954e0-…2``; the contract increments in RA §27's three
paragraphs, DOMAIN §20.2's three rows and DECISION_REGISTER v1.7.0).

The groups:

1. **atomic creation** (:func:`elc.world.bootstrap.create_world_with_bible`)
   — one short transaction lands the world, its revision-1 ``CURRENT``
   Bible, the AI cast (``world_actor`` + ``world_actor_profile`` pairs)
   and the durable player character, all or nothing; a same-shape replay
   is a zero-write no-op, a reshaped replay is ``CONFLICT``, a bad
   payload is refused before anything is written, and a mid-group
   failure (a dangling persona on the second actor) rolls the whole
   group back — proven by reading zero rows of every kind;
2. **the provider protocol face** (:mod:`elc.world.providers`) — the
   deterministic fake satisfies all three Protocols structurally; its
   outputs are configured and deterministic; and the **POV-safe context
   compilation hard door** holds physically: the recorded contexts a
   provider received carry only the POV's own faces (another actor's
   witnessed event, memory and private context are absent — the must_hide
   discipline's positive form), ``pov_context_of`` refuses another
   viewer's read, and the context's field set is frozen;
3. **the pipeline orchestrator** (:mod:`elc.world.pipeline`) — the
   §10.2-shaped chain end to end through the real library faces
   (create → chapter → scene → segments → User Gate → resolver →
   NCP-2 → auto-routed SCENE replan → settlement), with every canonical
   row asserted and the tick moving only through the commits; a crashed
   mid-scene drive replays its committed segments and continues; and
   ``resume`` routes the three routable recovery families (an
   ``ANSWERED`` gate re-adjudicated with the same ``submission_id``, a
   ``PENDING`` obligation consumed, a ``SETTLING`` chapter settled),
   idempotent on re-run;
4. **the discipline pins** — the orchestrator holds no transaction and
   spells no SQL, the creation service spells no DML (it composes the
   stores' ``*_tx`` arms), the store faces keep their own one short
   transaction, the new modules are not re-exported and start cold, and
   the ledger carries the V3-8a entries.
"""

from __future__ import annotations

import ast
import dataclasses
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from elc.platform.db.epoch import open_runtime_epoch
from elc.platform.db.migrations import apply_migrations
from elc.platform.types import DomainErrorCode, Err, Ok
from elc.world.action import (
    ActionStatus,
    Adjudication,
    GateStatus,
    ReplanScope,
    action_of,
    begin_resolving,
    commit_action,
    get_gate,
    open_gate,
    recovery_scan,
    replan_obligation,
    replan_request_id_for,
    submit_gate,
)
from elc.world.bible import BibleContent, SqliteBibleStore
from elc.world.bootstrap import ActorSeed, PlayerSeed, create_world_with_bible
from elc.world.cast import SqliteCastStore, StoryRole
from elc.world.cognition import v3_cognition_view
from elc.world.director import Director
from elc.world.memory import v3_memory_view
from elc.world.narrative import (
    ChapterStatus,
    SqliteNarrativeStore,
)
from elc.world.pipeline import GateBeat, Pipeline, SegmentBeat
from elc.world.providers import (
    DeterministicFakeProvider,
    DirectorPlanContext,
    DirectorProvider,
    PlannerProvider,
    PovContext,
    ResolverContext,
    ResolverProvider,
    ScenePlanContext,
    WriterProvider,
    pov_context_of,
)
from elc.world.scene import ScenePlanner
from elc.world.settlement import chapter_settlements_of
from elc.world.store import SqliteWorldStore
from elc.world.time import read_current_tick
from elc.world.types import StateEffect
from tests.conftest import SRC_ROOT

REPO = Path(__file__).resolve().parents[2]
AOCI_FILE = REPO / "aoci.code.txt"

PIPELINE_SOURCE = (SRC_ROOT / "world" / "pipeline.py").read_text(encoding="utf-8")
PIPELINE_TREE = ast.parse(PIPELINE_SOURCE)
PROVIDERS_SOURCE = (SRC_ROOT / "world" / "providers.py").read_text(
    encoding="utf-8"
)
PROVIDERS_TREE = ast.parse(PROVIDERS_SOURCE)
BOOTSTRAP_SOURCE = (SRC_ROOT / "world" / "bootstrap.py").read_text(
    encoding="utf-8"
)
BOOTSTRAP_TREE = ast.parse(BOOTSTRAP_SOURCE)
STORE_SOURCE = (SRC_ROOT / "world" / "store.py").read_text(encoding="utf-8")
STORE_TREE = ast.parse(STORE_SOURCE)
BIBLE_SOURCE = (SRC_ROOT / "world" / "bible.py").read_text(encoding="utf-8")
BIBLE_TREE = ast.parse(BIBLE_SOURCE)
CAST_SOURCE = (SRC_ROOT / "world" / "cast.py").read_text(encoding="utf-8")
CAST_TREE = ast.parse(CAST_SOURCE)

NOW = "2026-10-13T00:00:00+00:00"
LATER = "2026-10-13T01:00:00+00:00"
LATER2 = "2026-10-13T02:00:00+00:00"

TOWN = "world-town"
CH = "world-town-ch01"
SCENE = "world-town-ch01-s01"
SCENE2 = "world-town-ch01-s02"
GATE = "world-town-ch01-s01-g01"
ACTOR = "actor-lia"
PARTNER = "actor-bram"
PLAYER = "pc-you"

LIA_PRIVATE = "LIA_PRIVATE: she priced the tools herself"
BRAM_PRIVATE = "BRAM_PRIVATE: he watches the tide alone"
BRAM_SECRET_EVENT = "BRAM'S OWN QUIET LEDGER MOVE"

PROSE_1 = "The bell above the door answers before her voice does."
PROSE_2 = "She sets the ledger down, and the ice thins by a notch."

# ---------------------------------------------------------------------------
# fixtures / helpers (the V3-6 / V3-7 suites' own shapes)
# ---------------------------------------------------------------------------


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    """A fresh, fully migrated app.db with the production profile's
    foreign-keys-ON posture."""

    db = sqlite3.connect(tmp_path / "app.db")
    db.execute("PRAGMA foreign_keys=ON")
    apply_migrations(db)
    return db


@pytest.fixture()
def world_store(conn: sqlite3.Connection) -> SqliteWorldStore:
    return SqliteWorldStore(conn, open_runtime_epoch(conn))


@pytest.fixture()
def cast_store(conn: sqlite3.Connection) -> SqliteCastStore:
    return SqliteCastStore(conn, open_runtime_epoch(conn))


@pytest.fixture()
def bible_store(conn: sqlite3.Connection) -> SqliteBibleStore:
    return SqliteBibleStore(conn, open_runtime_epoch(conn))


@pytest.fixture()
def narrative(conn: sqlite3.Connection) -> SqliteNarrativeStore:
    return SqliteNarrativeStore(conn, open_runtime_epoch(conn))


@pytest.fixture()
def director(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
) -> Director:
    return Director(
        conn,
        world_store=world_store,
        cast_store=cast_store,
        bible_store=bible_store,
        narrative_store=narrative,
    )


@pytest.fixture()
def planner(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
) -> ScenePlanner:
    return ScenePlanner(
        conn,
        world_store=world_store,
        cast_store=cast_store,
        bible_store=bible_store,
        narrative_store=narrative,
    )


def _insert_card(conn: sqlite3.Connection, persona_id: str, name: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO character_card ("
        " character_id, persona_id, name, identity, personality,"
        " background, speech_style, \"values\", boundaries, opening,"
        " scenario, generation_policy, lore_refs, revision, status,"
        " is_builtin, created_at, updated_at"
        ") VALUES (?, ?, ?, 'i', 'p', 'b', 's', 'v', 'bo', 'o',"
        " 'sc', 'auto', '', 1, 'active', 1, ?, ?)",
        (f"cpkg-{persona_id}", persona_id, name, NOW, NOW),
    )


def _cast_seeds() -> tuple[ActorSeed, ...]:
    return (
        ActorSeed(
            actor_id=ACTOR,
            persona_id="persona-lia",
            story_role=StoryRole.PROTAGONIST,
            pov_eligible=True,
            pov_weight=1,
            long_term_drive="keep the shop open a winter longer",
            current_arc_seed="the order book is thinning",
            private_context=LIA_PRIVATE,
        ),
        ActorSeed(
            actor_id=PARTNER,
            persona_id="persona-bram",
            story_role=StoryRole.SUPPORTING,
            pov_eligible=True,
            pov_weight=2,
            long_term_drive="hold the tide schedule",
            current_arc_seed="the nets want mending",
            private_context=BRAM_PRIVATE,
        ),
    )


def _player_seed() -> PlayerSeed:
    return PlayerSeed(
        player_character_id=PLAYER,
        name="You",
        background="a newcomer off the evening coach",
        location="the inn",
        state="tired",
        knowledge_refs="a rumour about the mill",
    )


_UNSET = object()


def _create_town(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    *,
    actors: tuple[ActorSeed, ...] | None = None,
    player: PlayerSeed | None | object = _UNSET,
    bible: BibleContent | None = None,
    name: str = "Town",
    now: str = NOW,
):
    """The atomic creation service's own seed (the chain's step one).
    ``player`` rides the default seed when omitted; an explicit ``None``
    means a world that declares no player."""

    seeds = _cast_seeds() if actors is None else actors
    resolved_player = _player_seed() if player is _UNSET else player
    _insert_card(conn, "persona-lia", "Lia")
    _insert_card(conn, "persona-bram", "Bram")
    conn.commit()
    return create_world_with_bible(
        conn,
        world_store=world_store,
        bible_store=bible_store,
        cast_store=cast_store,
        world_id=TOWN,
        name=name,
        bible_revision_id=f"{TOWN}-bible-r1",
        bible=(
            BibleContent(premise="the town by the water")
            if bible is None
            else bible
        ),
        actors=seeds,
        player=resolved_player,
        now=now,
    )


def _scene_draft(
    *,
    pov: str = ACTOR,
    participants: tuple[str, ...] = (ACTOR, PLAYER),
    purpose: str = "first sight",
    must_hide: str = "the priced tools",
    entry_goals: str = "greet the newcomer",
) -> dict[str, Any]:
    return {
        "purpose": purpose,
        "place": "the bindery steps",
        "pov_actor_id": pov,
        "participants": list(participants),
        "planned_start_tick": 0,
        "entry_goals": entry_goals,
        "exit_condition": "the greeting lands or breaks",
        "elasticity": "may run long if you linger",
        "revealable": "the ledger's back page",
        "must_hide": must_hide,
    }


def _blueprint(
    scenes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if scenes is None:
        scenes = [_scene_draft()]
    return {
        "goal": "the newcomer and the shopkeeper truly meet",
        "dramatic_question": "Will the shop's silence open to a stranger?",
        "planned_start_tick": 0,
        "planned_end_tick": 600,
        "closing_pressure": "the first hard frost presses the order book",
        "desired_development": "trust grows by inches",
        "soft_outcomes": "a repair job, maybe",
        "chapter_questions_to_advance": "who is the letter from?",
        "scenes": scenes,
    }


def _ruling(
    *,
    interpretation: str = "You mean to help rather than to buy.",
    outcome: str = "Lia lets you hold the ledger; the ice thins.",
    actual_action: str = "you carry the ledger to the counter",
    consequences: str = "the shop's silence opens one notch",
    state_effects: tuple[StateEffect, ...] = (
        StateEffect(key="trust:lia", statement="warmed by one notch"),
    ),
    participants: tuple[str, ...] = (PLAYER, ACTOR),
    replan_scope: ReplanScope = ReplanScope.NONE,
) -> Adjudication:
    return Adjudication(
        interpretation=interpretation,
        outcome=outcome,
        actual_action=actual_action,
        consequences=consequences,
        state_effects=state_effects,
        participants=participants,
        replan_scope=replan_scope,
    )


def _fake(**kwargs: Any) -> DeterministicFakeProvider:
    return DeterministicFakeProvider(**kwargs)


def _pipeline(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    fake: DeterministicFakeProvider,
    *,
    action_duration_ticks: int = 7,
) -> Pipeline:
    return Pipeline(
        conn,
        world_store=world_store,
        cast_store=cast_store,
        bible_store=bible_store,
        narrative_store=narrative,
        writer_provider=fake,
        planner_provider=fake,
        director_provider=fake,
        resolver_provider=fake,
        action_duration_ticks=action_duration_ticks,
    )


def _count(conn: sqlite3.Connection, table: str) -> int:
    return int(
        conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    )


# ---------------------------------------------------------------------------
# 1. the atomic creation service
# ---------------------------------------------------------------------------


def test_create_world_with_bible_lands_the_group_in_one_transaction(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
) -> None:
    """The contract's sentence — world + initial Bible + player + cast,
    one short transaction, all or nothing: every row is present, the
    Bible sits ``CURRENT`` at revision 1, the cast carries its profiles
    and the outcome rides the stored records."""

    landed = _create_town(conn, world_store, cast_store, bible_store)
    assert isinstance(landed, Ok)
    outcome = landed.value
    assert outcome.world.world_id == TOWN
    assert outcome.world.name == "Town"
    assert outcome.world.template_world_id is None
    assert outcome.bible.world_id == TOWN
    assert outcome.bible.revision == 1
    assert outcome.bible.status.value == "CURRENT"
    assert outcome.bible.premise == "the town by the water"
    assert outcome.player is not None
    assert outcome.player.player_character_id == PLAYER
    assert [actor.actor_id for actor in outcome.actors] == [
        PARTNER,
        ACTOR,
    ]  # actor_id ascending (the durable order)
    assert [profile.actor_id for profile in outcome.profiles] == [
        PARTNER,
        ACTOR,
    ]
    asserted = {profile.story_role for profile in outcome.profiles}
    assert StoryRole.PROTAGONIST in asserted
    # the rows themselves, through the stores' own read faces
    assert world_store.get_world(TOWN) == outcome.world
    assert bible_store.current_bible(TOWN) == outcome.bible
    assert cast_store.player_character(TOWN) == outcome.player
    assert [row.actor_id for row in world_store.actors_of(TOWN)] == [
        PARTNER,
        ACTOR,
    ]
    assert _count(conn, "world") == 1
    assert _count(conn, "world_bible_revision") == 1
    assert _count(conn, "world_actor") == 2
    assert _count(conn, "world_actor_profile") == 2
    assert _count(conn, "world_player_character") == 1


def test_the_creation_replay_is_a_no_op_and_a_reshaped_replay_conflicts(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
) -> None:
    """The ``world_id`` idempotency key: the same shape rides back as
    the stored rows with zero write (stamps and versions included); a
    different name / Bible / profile / player presence is ``CONFLICT``
    and writes nothing."""

    first = _create_town(conn, world_store, cast_store, bible_store)
    assert isinstance(first, Ok)
    stamps = conn.execute(
        "SELECT created_at, updated_at, state_version"
        " FROM world_bible_revision"
    ).fetchall()
    versions = conn.execute(
        "SELECT actor_id, state_version FROM world_actor_profile"
        " ORDER BY actor_id"
    ).fetchall()

    replayed = _create_town(
        conn, world_store, cast_store, bible_store, now=LATER
    )
    assert isinstance(replayed, Ok)
    assert replayed.value == first.value  # the stored rows, byte for byte
    assert _count(conn, "world") == 1
    assert _count(conn, "world_bible_revision") == 1
    assert _count(conn, "world_actor") == 2
    assert _count(conn, "world_player_character") == 1
    assert (
        conn.execute(
            "SELECT created_at, updated_at, state_version"
            " FROM world_bible_revision"
        ).fetchall()
        == stamps
    )
    assert (
        conn.execute(
            "SELECT actor_id, state_version FROM world_actor_profile"
            " ORDER BY actor_id"
        ).fetchall()
        == versions
    )

    renamed = _create_town(
        conn, world_store, cast_store, bible_store, name="Other Town"
    )
    assert isinstance(renamed, Err)
    assert renamed.error.code is DomainErrorCode.CONFLICT
    assert "name / template" in renamed.error.message

    revised = _create_town(
        conn,
        world_store,
        cast_store,
        bible_store,
        bible=BibleContent(premise="a different premise"),
    )
    assert isinstance(revised, Err)
    assert revised.error.code is DomainErrorCode.CONFLICT
    assert "Bible" in revised.error.message

    reseeded = _create_town(
        conn,
        world_store,
        cast_store,
        bible_store,
        actors=(
            ActorSeed(
                actor_id=ACTOR,
                persona_id="persona-lia",
                story_role=StoryRole.MAJOR,  # was PROTAGONIST
            ),
        ),
    )
    assert isinstance(reseeded, Err)
    assert reseeded.error.code is DomainErrorCode.CONFLICT
    assert "cast roster" in reseeded.error.message

    no_player = _create_town(
        conn, world_store, cast_store, bible_store, player=None
    )
    assert isinstance(no_player, Err)
    assert no_player.error.code is DomainErrorCode.CONFLICT
    assert "player character presence" in no_player.error.message

    assert _count(conn, "world") == 1
    assert _count(conn, "world_bible_revision") == 1
    assert _count(conn, "world_player_character") == 1


def test_the_creation_refuses_a_bad_payload_before_writing_anything(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
) -> None:
    """The value-semantics refusals, judged before the transaction: an
    empty name, a duplicate actor id, a mistyped ``pov_weight`` and a
    non-``BibleContent`` payload all answer ``VALIDATION_FAILED`` and
    leave every table empty."""

    _insert_card(conn, "persona-lia", "Lia")
    conn.commit()

    def _create(**overrides: Any):
        kwargs: dict[str, Any] = {
            "world_id": TOWN,
            "name": "Town",
            "bible_revision_id": f"{TOWN}-bible-r1",
            "bible": BibleContent(premise="the town by the water"),
            "actors": (),
            "player": None,
        }
        kwargs.update(overrides)
        return create_world_with_bible(
            conn,
            world_store=world_store,
            bible_store=bible_store,
            cast_store=cast_store,
            now=NOW,
            **kwargs,
        )

    empty_name = _create(name="   ")
    assert isinstance(empty_name, Err)
    assert empty_name.error.code is DomainErrorCode.VALIDATION_FAILED

    duplicated = _create(
        actors=(
            ActorSeed(actor_id=ACTOR, persona_id="persona-lia"),
            ActorSeed(actor_id=ACTOR, persona_id="persona-lia"),
        )
    )
    assert isinstance(duplicated, Err)
    assert "appears twice" in duplicated.error.message

    mistyped = _create(
        actors=(
            ActorSeed(
                actor_id=ACTOR,
                persona_id="persona-lia",
                pov_weight=-1,
            ),
        )
    )
    assert isinstance(mistyped, Err)
    assert "pov_weight" in mistyped.error.message

    not_a_bible = _create(bible="not a BibleContent")
    assert isinstance(not_a_bible, Err)
    assert "BibleContent" in not_a_bible.error.message

    half_player = _create(player=PlayerSeed(PLAYER, name=""))
    assert isinstance(half_player, Err)
    assert "name" in half_player.error.message

    for table in (
        "world",
        "world_bible_revision",
        "world_actor",
        "world_actor_profile",
        "world_player_character",
    ):
        assert _count(conn, table) == 0, table


def test_a_mid_group_failure_rolls_the_whole_group_back(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
) -> None:
    """The injected failing arm: the second actor's persona is dangling,
    so the ``world_actor`` FK refuses **after** the world row, the Bible
    row, the first actor and its profile would have landed — and the
    whole group rolls back: zero rows of every kind, no residue."""

    _insert_card(conn, "persona-lia", "Lia")
    conn.commit()
    landed = create_world_with_bible(
        conn,
        world_store=world_store,
        bible_store=bible_store,
        cast_store=cast_store,
        world_id=TOWN,
        name="Town",
        bible_revision_id=f"{TOWN}-bible-r1",
        bible=BibleContent(premise="the town by the water"),
        actors=(
            ActorSeed(actor_id=ACTOR, persona_id="persona-lia"),
            ActorSeed(actor_id=PARTNER, persona_id="persona-nowhere"),
        ),
        player=_player_seed(),
        now=NOW,
    )
    assert isinstance(landed, Err)
    assert landed.error.code is DomainErrorCode.NOT_FOUND
    assert "rolled back" in landed.error.message
    for table in (
        "world",
        "world_bible_revision",
        "world_actor",
        "world_actor_profile",
        "world_player_character",
    ):
        assert _count(conn, table) == 0, table
    # and the retry with a real persona converges (the group is not
    # wedged: the rollback left nothing behind).
    _insert_card(conn, "persona-bram", "Bram")
    conn.commit()
    retried = create_world_with_bible(
        conn,
        world_store=world_store,
        bible_store=bible_store,
        cast_store=cast_store,
        world_id=TOWN,
        name="Town",
        bible_revision_id=f"{TOWN}-bible-r1",
        bible=BibleContent(premise="the town by the water"),
        actors=(
            ActorSeed(actor_id=ACTOR, persona_id="persona-lia"),
            ActorSeed(actor_id=PARTNER, persona_id="persona-bram"),
        ),
        player=_player_seed(),
        now=NOW,
    )
    assert isinstance(retried, Ok)
    assert _count(conn, "world_actor_profile") == 2


# ---------------------------------------------------------------------------
# 2. the provider protocol face and the POV-safe door
# ---------------------------------------------------------------------------


def test_the_fake_satisfies_all_four_protocols() -> None:
    """The structural contract: one class, four conformances (V3-8b
    splits the chapter arm out into the Director face) — the
    orchestration can hold it behind each Protocol's own type."""

    fake = _fake()
    assert isinstance(fake, WriterProvider)
    assert isinstance(fake, PlannerProvider)
    assert isinstance(fake, DirectorProvider)
    assert isinstance(fake, ResolverProvider)


def test_the_fake_is_deterministic_and_caller_influenceable(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """Configured outputs ride; unconfigured ones echo the context; an
    unscripted gate raises rather than inventing a verdict, and an
    unscripted initial Blueprint raises rather than inventing a plan
    (V3-8b: the Director face's initial arm has no content source to
    echo)."""

    assert isinstance(
        _create_town(conn, world_store, cast_store, bible_store), Ok
    )
    assert isinstance(
        director.open_next_chapter(TOWN, _blueprint(), NOW), Ok
    )
    opened = planner.open_scene(SCENE, NOW)
    assert isinstance(opened, Ok)
    opening = opened.value

    element = {
        "pov_actor_id": ACTOR,
        "participants": [ACTOR, PLAYER],
        "planned_start_tick": 0,
        "place": "the bindery steps",
        "entry_goals": "greet the newcomer",
        "exit_condition": "the greeting lands or breaks",
        "elasticity": "may run long if you linger",
        "revealable": "the ledger's back page",
        "must_hide": "the priced tools",
    }
    ruling = _ruling()
    fake = _fake(
        prose={(SCENE, 1): PROSE_1},
        scene_plan={"goal": "planned"},
        replan_elements=(element,),
        adjudications={GATE: ruling},
    )
    pov1 = pov_context_of(
        dossier=opening.dossier, context=opening.context, segment_seq=1
    )
    assert fake.write_segment(pov1) == PROSE_1
    pov2 = pov_context_of(
        dossier=opening.dossier, context=opening.context, segment_seq=2
    )
    echoed = fake.write_segment(pov2)
    assert str(pov2.segment_seq) in echoed and PROSE_1 != echoed

    plan_context = ScenePlanContext(
        world_id=TOWN,
        scene_id=SCENE,
        pov_actor_id=ACTOR,
        current_tick=opening.context.current_tick,
        element=element,
        cognition=opening.context.cognition,
        memory=opening.context.memory,
    )
    assert fake.plan_scene(plan_context) == {"goal": "planned"}
    assert dict(fake.replan_element(plan_context)) == element
    assert dict(fake.replan_element(plan_context)) == element  # echo now

    ruling = _ruling()
    player = cast_store.player_character(TOWN)
    assert player is not None
    profile = cast_store.actor_profile(ACTOR)
    assert profile is not None
    # the player character's own knowledge arms (V3-8c's F4): the reads
    # addressed to the player's identity, taken from the same world.
    player_cognition = v3_cognition_view(
        conn, world_id=TOWN, viewer_id=PLAYER
    )
    assert isinstance(player_cognition, Ok)
    player_memory = v3_memory_view(conn, world_id=TOWN, viewer_id=PLAYER)
    assert isinstance(player_memory, Ok)
    resolver_context = ResolverContext(
        gate_id=GATE,
        scene_id=SCENE,
        submission_id="sub-1",
        intent_text="I hand her the ledger.",
        selected_option=None,
        options=("hold the ledger", "step back"),
        bible=bible_store.current_bible(TOWN),
        current_facts=world_store.current_facts(TOWN),
        player_character=player,
        place=opening.dossier.place,
        participants=opening.dossier.participants,
        counterparts=(profile,),
        player_cognition=player_cognition.value,
        player_memory=player_memory.value,
        pov_actor_id=ACTOR,
        cognition=opening.context.cognition,
        memory=opening.context.memory,
        current_tick=opening.context.current_tick,
    )
    ruling = fake.adjudicate(resolver_context)
    assert ruling == _ruling()
    with pytest.raises(ValueError):
        fake.adjudicate(
            dataclasses.replace(resolver_context, gate_id="no-gate")
        )
    # the Director face's initial arm: configured payloads ride, an
    # unscripted draft is the script's gap.
    director_context = director.context(TOWN)
    draft_context = DirectorPlanContext(
        director_context=director_context,
        chapter_id=None,
        replan_request_id=None,
        trigger=None,
        blueprint=None,
    )
    scripted = _fake(blueprints=(_blueprint(),))
    assert dict(scripted.draft_blueprint(draft_context)) == _blueprint()
    with pytest.raises(ValueError):
        fake.draft_blueprint(draft_context)
    # the recordings are the pins' evidence
    assert [c.segment_seq for c in fake.segment_contexts] == [1, 2]
    assert len(fake.plan_contexts) == 1
    assert len(fake.replan_contexts) == 2
    assert len(fake.resolver_contexts) == 2
    assert len(fake.blueprint_contexts) == 1


def test_pov_context_of_refuses_another_viewers_read(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The door's own refusal: a SceneContext addressed to another
    viewer cannot be compiled into this dossier's input — the honest
    ``ValueError``, never a silently mis-addressed context."""

    assert isinstance(
        _create_town(conn, world_store, cast_store, bible_store), Ok
    )
    assert isinstance(
        director.open_next_chapter(TOWN, _blueprint(), NOW), Ok
    )
    opened = planner.open_scene(SCENE, NOW)
    assert isinstance(opened, Ok)
    opening = opened.value
    misaddressed = dataclasses.replace(
        opening.context, pov_actor_id=PARTNER
    )
    with pytest.raises(ValueError):
        pov_context_of(
            dossier=opening.dossier, context=misaddressed, segment_seq=1
        )


def test_the_pov_context_refuses_a_mis_addressed_inner_view(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The last-hop address check (the review's F2): a SceneContext whose
    ``pov_actor_id`` matches the dossier but whose cognition or memory
    view is addressed to ANOTHER viewer must not compile — the signature
    is the door only when the inner reads share the POV's address."""

    assert isinstance(
        _create_town(conn, world_store, cast_store, bible_store), Ok
    )
    assert isinstance(
        director.open_next_chapter(TOWN, _blueprint(), NOW), Ok
    )
    opened = planner.open_scene(SCENE, NOW)
    assert isinstance(opened, Ok)
    opening = opened.value
    # the context's own address matches the dossier's POV, but the
    # cognition read inside it was taken for someone else.
    bad_cognition = dataclasses.replace(
        opening.context,
        cognition=dataclasses.replace(
            opening.context.cognition, viewer_id=PARTNER
        ),
    )
    with pytest.raises(ValueError):
        pov_context_of(
            dossier=opening.dossier, context=bad_cognition, segment_seq=1
        )
    # the memory read addressed to someone else.
    bad_memory = dataclasses.replace(
        opening.context,
        memory=dataclasses.replace(opening.context.memory, viewer_id=PARTNER),
    )
    with pytest.raises(ValueError):
        pov_context_of(
            dossier=opening.dossier, context=bad_memory, segment_seq=1
        )


def test_the_pov_context_field_set_is_frozen() -> None:
    """The shape pin: the compiled context carries exactly the POV's own
    faces — no field for a profile, a private context or another
    participant's read exists to leak from."""

    names = tuple(field.name for field in dataclasses.fields(PovContext))
    assert names == (
        "scene_id",
        "segment_seq",
        "pov_actor_id",
        "participants",
        "place",
        "entry_goals",
        "exit_condition",
        "revealable",
        "must_hide",
        "current_tick",
        "cognition",
        "memory",
    )
    assert "private" not in " ".join(names)


def test_the_provider_contexts_carry_only_the_pov_visible_faces(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The V3-5R hard door, behaviorally: Bram's scene commits an event
    his memory alone holds; Lia's scene is then driven and the contexts
    her provider received carry **nothing** of Bram's — his event, his
    memory's text and his profile's private context are absent, while
    her own earlier event (the second segment's compile) is present.
    The contrast witness: Bram's own memory view does hold the event, so
    the absence is addressing, not emptiness."""

    assert isinstance(
        _create_town(conn, world_store, cast_store, bible_store), Ok
    )
    assert isinstance(
        director.open_next_chapter(
            TOWN,
            _blueprint(
                scenes=[
                    _scene_draft(),
                    _scene_draft(
                        pov=PARTNER,
                        participants=(PARTNER,),
                        purpose="the tide watch",
                    ),
                ]
            ),
            NOW,
        ),
        Ok,
    )
    # Bram's own scene is driven first: one segment whose narration is
    # his private knowledge — an event Lia does not witness (she is not
    # among its participants).
    fake = _fake(
        prose={
            (SCENE2, 1): "Bram turns the quiet page nobody else sees.",
            (SCENE, 1): PROSE_1,
            (SCENE, 2): PROSE_2,
        }
    )
    pipeline = _pipeline(
        conn, world_store, cast_store, bible_store, narrative, fake
    )
    bram_drive = pipeline.run_scene(
        SCENE2,
        (
            SegmentBeat(duration_ticks=1, is_last_segment=True),
        ),
        NOW,
    )
    assert isinstance(bram_drive, Ok)
    bram_context = fake.segment_contexts[0]
    assert bram_context.pov_actor_id == PARTNER
    assert bram_context.cognition.viewer_id == PARTNER
    assert bram_context.memory.viewer_id == PARTNER

    lia_drive = pipeline.run_scene(
        SCENE,
        (
            SegmentBeat(duration_ticks=3),
            SegmentBeat(duration_ticks=2, is_last_segment=True),
        ),
        LATER,
    )
    assert isinstance(lia_drive, Ok)
    lia_contexts = fake.segment_contexts[1:]
    assert len(lia_contexts) == 2
    first, second = lia_contexts
    # every recorded context addresses Lia alone.
    for context in lia_contexts:
        assert context.pov_actor_id == ACTOR
        assert context.cognition.viewer_id == ACTOR
        assert context.memory.viewer_id == ACTOR
        # Bram's hidden knowledge is nowhere in the compiled input.
        assert BRAM_SECRET_EVENT not in str(context)
        assert BRAM_PRIVATE not in str(context)
        assert LIA_PRIVATE not in str(context)
    # the first segment's compile sees nothing yet; the second's sees
    # exactly Lia's own first event — never Bram's.
    assert first.memory.memories == ()
    assert first.cognition.witnessed == ()
    assert len(second.memory.memories) == 1
    assert (
        second.memory.memories[0].source_event_id == f"{SCENE}-e0001"
    )
    assert second.memory.memories[0].content == PROSE_1
    event_ids = {event.event_id for event in second.cognition.witnessed}
    assert event_ids == {f"{SCENE}-e0001"}
    assert f"{SCENE2}-e0001" not in event_ids
    assert all(
        event.event_id != f"{SCENE2}-e0001"
        for event in bram_context.cognition.witnessed
    )
    # the contrast witness: Bram's own view does hold his event now —
    # the record exists; Lia's contexts simply cannot address it.
    bram_view = v3_memory_view(
        conn, world_id=TOWN, viewer_id=PARTNER
    )
    assert isinstance(bram_view, Ok)
    assert [row.source_event_id for row in bram_view.value.memories] == [
        f"{SCENE2}-e0001"
    ]


# ---------------------------------------------------------------------------
# 3. the pipeline orchestrator: the §10.2-shaped chain
# ---------------------------------------------------------------------------


def test_the_pipeline_drives_the_gold_scenario_shaped_chain(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
) -> None:
    """create → chapter → scene → segments → User Gate → NCP-1 → the
    resolver's verdict → NCP-2 → the auto-routed SCENE replan → the
    settling segment (closing the gate) → settlement. Every canonical
    row lands; the tick moves only through the commits; the replanned
    dossier is the one the continuation writes from."""

    assert isinstance(
        _create_town(conn, world_store, cast_store, bible_store), Ok
    )
    replanned_element = {
        "pov_actor_id": ACTOR,
        "participants": [ACTOR, PLAYER],
        "planned_start_tick": 0,
        "place": "the counter",
        "entry_goals": "let the ledger speak for you",
        "exit_condition": "the ledger is set down",
        "elasticity": "short",
        "revealable": "the ledger's back page",
        "must_hide": "the names on the last page",
    }
    ruling = _ruling(replan_scope=ReplanScope.SCENE)
    fake = _fake(
        prose={(SCENE, 1): PROSE_1, (SCENE, 2): PROSE_2},
        adjudications={GATE: ruling},
        replan_elements=(replanned_element,),
    )
    pipeline = _pipeline(
        conn, world_store, cast_store, bible_store, narrative, fake
    )

    chapter = pipeline.open_chapter(TOWN, _blueprint(), NOW)
    assert isinstance(chapter, Ok)
    assert chapter.value.chapter.chapter_id == CH
    chapter_record = narrative.get_chapter(CH)
    assert chapter_record is not None
    assert chapter_record.status is ChapterStatus.PLANNED
    assert chapter_record.opened_at_tick is None

    driven = pipeline.run_scene(
        SCENE,
        (
            SegmentBeat(duration_ticks=3),
            GateBeat(
                gate_seq=1,
                options=("hold the ledger", "step back"),
                submission_id="sub-1",
                intent_text="I hold the ledger and say nothing.",
            ),
            SegmentBeat(duration_ticks=2, is_last_segment=True),
        ),
        NOW,
    )
    assert isinstance(driven, Ok)
    run = driven.value
    assert [outcome.actual_end_tick for outcome in run.segments] == [3, 12]
    assert len(run.gates) == 1
    assert run.gates[0].gate_id == GATE
    assert run.gates[0].status is GateStatus.CLOSED  # the continuation resumed past it
    assert run.gates[0].opened_at_tick == 3
    assert len(run.actions) == 1
    action_outcome = run.actions[0]
    assert action_outcome.actual_start_tick == 3
    assert action_outcome.actual_end_tick == 10
    assert action_outcome.replan_scope is ReplanScope.SCENE
    assert len(run.replans) == 1
    assert run.replans[0].scope is ReplanScope.SCENE
    assert run.replans[0].target_ref == f"{SCENE}-d2"

    # the resolver's verdict is the durable ruling, column for column.
    action = action_of(conn, GATE)
    assert action is not None
    assert action.status is ActionStatus.COMMITTED
    assert action.interpretation == ruling.interpretation
    assert action.outcome == ruling.outcome
    assert action.actual_action == ruling.actual_action
    assert action.consequences == ruling.consequences
    assert action.state_effects == ruling.state_effects
    assert action.participants == ruling.participants
    assert action.replan_scope is ReplanScope.SCENE
    assert action.submission_id == "sub-1"
    # the resolver's own provider input was world-authoritative (V3-8b:
    # the CURRENT Bible, the settled facts, the player's row beside the
    # user's words — the intent comes from the durable submission, never
    # an invention) and carried the POV read for what the player knows.
    resolver_context = fake.resolver_contexts[0]
    assert resolver_context.intent_text == (
        "I hold the ledger and say nothing."
    )
    assert resolver_context.submission_id == "sub-1"
    assert resolver_context.bible is not None
    assert resolver_context.place == "the bindery steps"
    assert resolver_context.player_character is not None
    assert resolver_context.player_character.player_character_id == PLAYER
    assert [
        profile.actor_id for profile in resolver_context.counterparts
    ] == [ACTOR]
    assert resolver_context.pov_actor_id == ACTOR
    assert resolver_context.memory.viewer_id == ACTOR
    # V3-8c's F4: the player character's own knowledge arms ride beside
    # the POV's narrative face, addressed to the player's identity.
    assert resolver_context.player_cognition is not None
    assert resolver_context.player_cognition.viewer_id == PLAYER
    assert resolver_context.player_memory is not None
    assert resolver_context.player_memory.viewer_id == PLAYER

    # the canonical rows (the lineage table carries the two SEGMENT rows
    # and the ruling's ACTION_OUTCOME row).
    assert _count(conn, "narrative_passage") == 2
    assert _count(conn, "segment_commit") == 3
    assert [
        str(row[0])
        for row in conn.execute(
            "SELECT kind FROM segment_commit ORDER BY commit_id"
        ).fetchall()
    ] == ["ACTION_OUTCOME", "SEGMENT", "SEGMENT"]
    assert _count(conn, "world_event") == 3  # two segments + the ruling
    assert _count(conn, "actor_memory") == 6  # 2 + 2 + 2 participants
    passages = conn.execute(
        "SELECT passage_id, outcome_ref FROM narrative_passage"
        " ORDER BY passage_id"
    ).fetchall()
    assert passages[0][1] is None
    assert passages[1][1] == f"{GATE}-a"  # the V3-6R continuation chain
    event = conn.execute(
        "SELECT narration FROM world_event"
        " WHERE event_id = ?",
        (action_outcome.event_id,),
    ).fetchone()
    assert event is not None and str(event[0]) == ruling.outcome
    fact = conn.execute(
        "SELECT statement FROM world_state_fact WHERE status = 'CURRENT'"
    ).fetchone()
    assert fact is not None and str(fact[0]) == "warmed by one notch"
    # the ruling's intent text never entered the canon.
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM world_event WHERE narration LIKE"
            " '%I hold the ledger%'"
        ).fetchone()[0]
        == 0
    )

    # the replanned plan face is the one that stands, and the scene is
    # committed (the last segment's SCENE COMMIT alias).
    adopted = narrative.adopted_dossier(SCENE)
    assert adopted is not None
    assert adopted.dossier_id == f"{SCENE}-d2"
    assert adopted.dossier_revision == 2
    assert adopted.must_hide == "the names on the last page"
    scene_row = narrative.get_scene(SCENE)
    assert scene_row is not None
    assert scene_row.actual_start_tick == 0
    assert scene_row.actual_end_tick == 12

    # the tick moved only through the commits: 3 + 7 + 2.
    tick = read_current_tick(conn, TOWN)
    assert isinstance(tick, Ok)
    assert tick.value == 12

    settled = pipeline.settle(CH, LATER)
    assert isinstance(settled, Ok)
    assert settled.value.chapter_id == CH
    assert settled.value.summary.count("\n") == 2  # three lineage lines
    assert ruling.outcome in settled.value.summary
    chapter_record = narrative.get_chapter(CH)
    assert chapter_record is not None
    assert chapter_record.status is ChapterStatus.CLOSED
    assert chapter_record.closed_at_tick == 12
    assert [row.chapter_id for row in chapter_settlements_of(conn, TOWN)] == [
        CH
    ]
    # the settlement compressed; it produced no new fact and no tick.
    assert _count(conn, "world_event") == 3
    assert _count(conn, "narrative_passage") == 2
    tick_after = read_current_tick(conn, TOWN)
    assert isinstance(tick_after, Ok)
    assert tick_after.value == 12


def test_a_crashed_scene_drive_replays_and_continues(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
) -> None:
    """The crash window between beats: the first drive commits its
    single segment and stops (the scene stays ``ACTIVE`` — no ruling
    stands, so nothing else is unfinished); ``resume`` reports the
    active scene without routing it; re-driving the same **script** with
    the closing beat appended replays the committed segment (zero second
    rows) and lands only the new one.

    **Migrated by V3-8b**: this fixture used to crash *after a
    committed ruling* — that window is the HARD GATE's now (``resume``
    drives its continuation itself; its own pin lives in the V3-8b
    suite, and the ``first_segment_seq`` knob this test once leaned on
    is gone with the script law), so the no-gate crash keeps the
    caller's re-drive as the resuming face."""

    assert isinstance(
        _create_town(conn, world_store, cast_store, bible_store), Ok
    )
    fake = _fake(prose={(SCENE, 1): PROSE_1, (SCENE, 2): PROSE_2})
    pipeline = _pipeline(
        conn, world_store, cast_store, bible_store, narrative, fake
    )
    assert isinstance(pipeline.open_chapter(TOWN, _blueprint(), NOW), Ok)
    beats = (SegmentBeat(duration_ticks=3),)
    first = pipeline.run_scene(SCENE, beats, NOW)
    assert isinstance(first, Ok)
    assert first.value.gates == ()
    assert _count(conn, "narrative_passage") == 1
    assert _count(conn, "world_event") == 1  # the segment's own

    walk = pipeline.resume(TOWN, LATER)
    assert isinstance(walk, Ok)
    assert walk.value.gates_committed == ()
    assert walk.value.replans_consumed == ()
    assert walk.value.continuations_driven == ()
    assert walk.value.chapters_settled == ()
    assert walk.value.active_scene_ids == (SCENE,)

    second = pipeline.run_scene(
        SCENE,
        beats + (SegmentBeat(duration_ticks=2, is_last_segment=True),),
        LATER,
    )
    assert isinstance(second, Ok)
    run = second.value
    # the replayed segment answers its stored outcome (end tick 3 — no
    # second advance); the fresh one lands at 5.
    assert [outcome.actual_end_tick for outcome in run.segments] == [3, 5]
    assert [outcome.passage_id for outcome in run.segments] == [
        f"{SCENE}-p0001",
        f"{SCENE}-p0002",
    ]
    assert run.opening.dossier.dossier_id == f"{SCENE}-d1"
    # exactly one row of each kind for the replayed pair; the tick
    # advanced once per distinct commit.
    assert _count(conn, "narrative_passage") == 2
    assert _count(conn, "segment_commit") == 2
    assert _count(conn, "world_event") == 2
    assert _count(conn, "user_action") == 0
    tick = read_current_tick(conn, TOWN)
    assert isinstance(tick, Ok)
    assert tick.value == 5


def test_a_completed_scene_drive_is_not_re_runnable(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
) -> None:
    """The honest replay boundary: a drive whose last segment closed the
    scene refuses to re-drive it (``COMMITTED`` is past this door) —
    committed canon is not re-played by the orchestrator."""

    assert isinstance(
        _create_town(conn, world_store, cast_store, bible_store), Ok
    )
    fake = _fake(prose={(SCENE, 1): PROSE_1})
    pipeline = _pipeline(
        conn, world_store, cast_store, bible_store, narrative, fake
    )
    assert isinstance(pipeline.open_chapter(TOWN, _blueprint(), NOW), Ok)
    beats = (SegmentBeat(duration_ticks=3, is_last_segment=True),)
    assert isinstance(pipeline.run_scene(SCENE, beats, NOW), Ok)
    again = pipeline.run_scene(SCENE, beats, LATER)
    assert isinstance(again, Err)
    assert again.error.code is DomainErrorCode.VALIDATION_FAILED
    assert _count(conn, "narrative_passage") == 1


# ---------------------------------------------------------------------------
# 4. the crash-resume routing
# ---------------------------------------------------------------------------


def _open_gate_and_submit(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The crash point after NCP-1, built through the library faces: the
    town, the chapter, the active scene, the gate ``ANSWERED``."""

    assert isinstance(
        _create_town(conn, world_store, cast_store, bible_store), Ok
    )
    assert isinstance(
        director.open_next_chapter(TOWN, _blueprint(), NOW), Ok
    )
    assert isinstance(planner.open_scene(SCENE, NOW), Ok)
    assert isinstance(
        open_gate(
            conn,
            scene_id=SCENE,
            gate_seq=1,
            options=("hold the ledger", "step back"),
            now=NOW,
        ),
        Ok,
    )
    assert isinstance(
        submit_gate(
            conn,
            gate_id=GATE,
            submission_id="sub-1",
            intent_text="I hold the ledger and say nothing.",
            now=NOW,
        ),
        Ok,
    )


def test_resume_re_adjudicates_an_answered_gate_with_the_same_submission(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The RA §28 window "NCP-1 后崩溃": the gate is ``ANSWERED``; the
    resolver provider answers the same gate again (the same ruling) and
    ``commit_action`` lands the unique outcome with the **stored**
    ``submission_id``. The walk that commits the ruling carries its
    continuation obligation into the **next** walk (V3-8b: the walk
    routes the families its scan found), which drives the continuation
    and closes the gate; the third walk is then the zero-write no-op."""

    _open_gate_and_submit(
        conn, world_store, cast_store, bible_store, director, planner
    )
    ruling = _ruling()
    fake = _fake(adjudications={GATE: ruling})
    pipeline = _pipeline(
        conn, world_store, cast_store, bible_store, narrative, fake
    )
    walk = pipeline.resume(TOWN, LATER)
    assert isinstance(walk, Ok)
    assert walk.value.gates_committed == (GATE,)
    assert walk.value.replans_consumed == ()
    assert walk.value.continuations_driven == ()
    assert walk.value.chapters_settled == ()
    gate = get_gate(conn, GATE)
    assert gate is not None and gate.status is GateStatus.COMMITTED
    action = action_of(conn, GATE)
    assert action is not None
    assert action.status is ActionStatus.COMMITTED
    assert action.submission_id == "sub-1"
    assert action.outcome == ruling.outcome
    assert fake.resolver_contexts[0].submission_id == "sub-1"
    assert fake.resolver_contexts[0].gate_id == GATE
    assert _count(conn, "world_event") == 1
    assert _count(conn, "user_action") == 1
    tick = read_current_tick(conn, TOWN)
    assert isinstance(tick, Ok)
    assert tick.value == 7  # the ruling's own duration

    # V3-8b: the second walk finds the committed-unclosed gate (the
    # ruling nobody resumed past) and drives its first continuation
    # passage — the gate closes in that same commit.
    again = pipeline.resume(TOWN, LATER2)
    assert isinstance(again, Ok)
    assert again.value.gates_committed == ()
    assert again.value.replans_consumed == ()
    assert again.value.continuations_driven == (GATE,)
    assert again.value.chapters_settled == ()
    gate = get_gate(conn, GATE)
    assert gate is not None and gate.status is GateStatus.CLOSED
    assert _count(conn, "narrative_passage") == 1
    assert _count(conn, "world_event") == 2
    assert _count(conn, "user_action") == 1
    tick_again = read_current_tick(conn, TOWN)
    assert isinstance(tick_again, Ok)
    assert tick_again.value == 8  # the continuation's one-tick beat

    # the third walk: nothing left to route — the zero-write no-op.
    third = pipeline.resume(TOWN, LATER2)
    assert isinstance(third, Ok)
    assert third.value.continuations_driven == ()
    assert _count(conn, "narrative_passage") == 1
    assert _count(conn, "world_event") == 2
    tick_third = read_current_tick(conn, TOWN)
    assert isinstance(tick_third, Ok)
    assert tick_third.value == 8


def test_resume_consumes_a_pending_replan_obligation(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The V3-6R window: NCP-2 landed with ``replan_scope = SCENE`` and
    the obligation sits ``PENDING``; ``resume`` feeds the Planner
    provider the ruling scene's POV-safe context and consumes the
    obligation through ``replan_scene`` (a new adopted dossier). Re-run
    is a no-op."""

    _open_gate_and_submit(
        conn, world_store, cast_store, bible_store, director, planner
    )
    assert isinstance(
        begin_resolving(conn, gate_id=GATE, now=LATER), Ok
    )
    committed = commit_action(
        conn,
        world_store=world_store,
        narrative_store=narrative,
        gate_id=GATE,
        submission_id="sub-1",
        adjudication=_ruling(replan_scope=ReplanScope.SCENE),
        duration_ticks=7,
        now=LATER,
    )
    assert isinstance(committed, Ok)
    request = replan_request_id_for(GATE, "sub-1")
    obligation = replan_obligation(conn, request)
    assert obligation is not None
    assert obligation.status.value == "PENDING"

    element = {
        "pov_actor_id": ACTOR,
        "participants": [ACTOR, PLAYER],
        "planned_start_tick": 0,
        "place": "the counter",
        "entry_goals": "let the ledger speak for you",
        "exit_condition": "the ledger is set down",
        "elasticity": "short",
        "revealable": "the ledger's back page",
        "must_hide": "the names on the last page",
    }
    fake = _fake(replan_elements=(element,))
    pipeline = _pipeline(
        conn, world_store, cast_store, bible_store, narrative, fake
    )
    walk = pipeline.resume(TOWN, LATER2)
    assert isinstance(walk, Ok)
    assert len(walk.value.replans_consumed) == 1
    consumed = walk.value.replans_consumed[0]
    assert consumed.replan_request_id == request
    assert consumed.scope is ReplanScope.SCENE
    assert consumed.target_ref == f"{SCENE}-d2"
    assert fake.replan_contexts[0].scene_id == SCENE
    assert fake.replan_contexts[0].pov_actor_id == ACTOR
    assert fake.replan_contexts[0].memory.viewer_id == ACTOR
    applied = replan_obligation(conn, request)
    assert applied is not None and applied.status.value == "APPLIED"
    adopted = narrative.adopted_dossier(SCENE)
    assert adopted is not None
    assert adopted.dossier_id == f"{SCENE}-d2"
    assert adopted.entry_goals == "let the ledger speak for you"
    assert walk.value.gates_committed == ()

    again = pipeline.resume(TOWN, LATER2)
    assert isinstance(again, Ok)
    assert again.value.replans_consumed == ()
    assert len(narrative.dossiers_of(SCENE)) == 2


def test_resume_consumes_a_pending_chapter_obligation(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The CHAPTER arm of the routing — **migrated by V3-8b's HIGH-3**:
    the obligation's payload comes from the **Director provider's**
    ``replan_blueprint`` (the chapter's plan is the world's, fed the
    full ``DirectorContext`` plus the committed ruling that triggered
    it — never the POV-limited Planner provider) and lands through
    ``Director.apply_action_replan`` — a new adopted plan revision.
    (The echo default makes the revised shape equal the current one; the
    revision still mints and the obligation still completes.)"""

    _open_gate_and_submit(
        conn, world_store, cast_store, bible_store, director, planner
    )
    assert isinstance(
        begin_resolving(conn, gate_id=GATE, now=LATER), Ok
    )
    committed = commit_action(
        conn,
        world_store=world_store,
        narrative_store=narrative,
        gate_id=GATE,
        submission_id="sub-1",
        adjudication=_ruling(replan_scope=ReplanScope.CHAPTER),
        duration_ticks=7,
        now=LATER,
    )
    assert isinstance(committed, Ok)
    request = replan_request_id_for(GATE, "sub-1")
    obligation = replan_obligation(conn, request)
    assert obligation is not None
    assert obligation.scope is ReplanScope.CHAPTER

    fake = _fake()
    pipeline = _pipeline(
        conn, world_store, cast_store, bible_store, narrative, fake
    )
    walk = pipeline.resume(TOWN, LATER2)
    assert isinstance(walk, Ok)
    assert len(walk.value.replans_consumed) == 1
    consumed = walk.value.replans_consumed[0]
    assert consumed.scope is ReplanScope.CHAPTER
    assert consumed.target_ref == f"{CH}-bp-r2"
    blueprint_context = fake.blueprint_contexts[0]
    # the plan face's production is the Director's: the full
    # DirectorContext rides, and so does the triggering ruling.
    assert blueprint_context.chapter_id == CH
    assert blueprint_context.replan_request_id == request
    assert blueprint_context.director_context.world_id == TOWN
    assert blueprint_context.director_context.bible is not None
    assert blueprint_context.director_context.cast.player_character is not None
    assert blueprint_context.trigger is not None
    assert blueprint_context.trigger.user_action_id == f"{GATE}-a"
    assert blueprint_context.trigger.intent_text == (
        "I hold the ledger and say nothing."
    )
    assert blueprint_context.trigger.replan_scope is ReplanScope.CHAPTER
    assert "scenes" in blueprint_context.blueprint
    # the POV-limited context never entered this arm.
    assert fake.replan_contexts == []
    assert fake.plan_contexts == []
    applied = replan_obligation(conn, request)
    assert applied is not None and applied.status.value == "APPLIED"
    plans = narrative.plans_of(CH)
    assert [plan.plan_revision for plan in plans] == [1, 2]
    assert plans[-1].chapter_plan_id == f"{CH}-bp-r2"
    assert plans[-1].status.value == "ADOPTED"

    # V3-8b's HARD GATE rides the same walk: the committed-unclosed gate
    # the obligation came from is a continuation nobody resumed past —
    # the walk drove its first continuation passage after the plan
    # change landed.
    assert walk.value.continuations_driven == (GATE,)
    left = get_gate(conn, GATE)
    assert left is not None and left.status is GateStatus.CLOSED

    again = pipeline.resume(TOWN, LATER2)
    assert isinstance(again, Ok)
    assert again.value.replans_consumed == ()
    assert len(narrative.plans_of(CH)) == 2


def test_resume_settles_a_settling_chapter(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
) -> None:
    """The NCP-4 window: the chapter stands ``SETTLING`` (the crash
    inside the settlement); ``resume`` lands the one-version settlement
    and closes the chapter — the tick never moves, no fact is written.
    Re-run is a no-op."""

    assert isinstance(
        _create_town(conn, world_store, cast_store, bible_store), Ok
    )
    fake = _fake(prose={(SCENE, 1): PROSE_1})
    pipeline = _pipeline(
        conn, world_store, cast_store, bible_store, narrative, fake
    )
    assert isinstance(pipeline.open_chapter(TOWN, _blueprint(), NOW), Ok)
    driven = pipeline.run_scene(
        SCENE,
        (SegmentBeat(duration_ticks=3, is_last_segment=True),),
        NOW,
    )
    assert isinstance(driven, Ok)
    chapter = narrative.get_chapter(CH)
    assert chapter is not None and chapter.status is ChapterStatus.ACTIVE
    flipped = narrative.settle_chapter(
        CH, LATER, expected_state_version=chapter.state_version
    )
    assert isinstance(flipped, Ok)
    assert flipped.value.status is ChapterStatus.SETTLING

    walk = pipeline.resume(TOWN, LATER2)
    assert isinstance(walk, Ok)
    assert walk.value.chapters_settled == (CH,)
    assert walk.value.gates_committed == ()
    assert walk.value.replans_consumed == ()
    assert walk.value.active_scene_ids == ()  # the scene was closed
    chapter = narrative.get_chapter(CH)
    assert chapter is not None and chapter.status is ChapterStatus.CLOSED
    assert chapter.closed_at_tick == 3
    assert _count(conn, "chapter_settlement") == 1
    assert _count(conn, "world_event") == 1  # only the segment's own
    tick = read_current_tick(conn, TOWN)
    assert isinstance(tick, Ok)
    assert tick.value == 3

    again = pipeline.resume(TOWN, LATER2)
    assert isinstance(again, Ok)
    assert again.value.chapters_settled == ()
    assert _count(conn, "chapter_settlement") == 1


def test_settle_refuses_a_chapter_that_does_not_exist(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
) -> None:
    """The settle face's dangling read: an unknown chapter is
    ``NOT_FOUND``, and a ``PLANNED`` chapter (nothing committed to
    compress) is the settlement face's own refusal."""

    fake = _fake()
    pipeline = _pipeline(
        conn, world_store, cast_store, bible_store, narrative, fake
    )
    missing = pipeline.settle("no-such-chapter", NOW)
    assert isinstance(missing, Err)
    assert missing.error.code is DomainErrorCode.NOT_FOUND

    assert isinstance(
        _create_town(conn, world_store, cast_store, bible_store), Ok
    )
    assert isinstance(pipeline.open_chapter(TOWN, _blueprint(), NOW), Ok)
    planned = pipeline.settle(CH, NOW)
    assert isinstance(planned, Err)
    assert planned.error.code is DomainErrorCode.VALIDATION_FAILED
    assert _count(conn, "chapter_settlement") == 0


def test_resume_is_world_scoped(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The walk routes one world's families only: a second world's
    ``ANSWERED`` gate is not touched by the first world's resume."""

    _open_gate_and_submit(
        conn, world_store, cast_store, bible_store, director, planner
    )
    # a second, unrelated world with its own answered gate.
    _insert_card(conn, "persona-other", "Other")
    conn.commit()
    other = create_world_with_bible(
        conn,
        world_store=world_store,
        bible_store=bible_store,
        cast_store=cast_store,
        world_id="world-other",
        name="Other",
        bible_revision_id="world-other-bible-r1",
        bible=BibleContent(premise="elsewhere"),
        actors=(
            ActorSeed(
                actor_id="actor-other",
                persona_id="persona-other",
                pov_eligible=True,
            ),
        ),
        player=PlayerSeed("pc-other", name="Someone"),
        now=NOW,
    )
    assert isinstance(other, Ok)
    other_blueprint = _blueprint(
        scenes=[
            _scene_draft(
                pov="actor-other",
                participants=("actor-other", "pc-other"),
            )
        ]
    )
    assert isinstance(
        director.open_next_chapter("world-other", other_blueprint, LATER),
        Ok,
    )
    other_scene = "world-other-ch01-s01"
    # the blueprint's scene id derives from the chapter id.
    assert isinstance(planner.open_scene(other_scene, LATER), Ok)
    assert isinstance(
        open_gate(
            conn,
            scene_id=other_scene,
            gate_seq=1,
            options=("stay", "go"),
            now=LATER,
        ),
        Ok,
    )
    assert isinstance(
        submit_gate(
            conn,
            gate_id=f"{other_scene}-g01",
            submission_id="sub-other",
            intent_text="I stay.",
            now=LATER,
        ),
        Ok,
    )
    fake = _fake(adjudications={GATE: _ruling()})
    pipeline = _pipeline(
        conn, world_store, cast_store, bible_store, narrative, fake
    )
    walk = pipeline.resume(TOWN, LATER2)
    assert isinstance(walk, Ok)
    assert walk.value.gates_committed == (GATE,)
    other_gate = get_gate(conn, f"{other_scene}-g01")
    assert other_gate is not None and other_gate.status is GateStatus.ANSWERED
    scan = recovery_scan(conn, narrative_store=narrative)
    assert isinstance(scan, Ok)
    assert [gate.gate_id for gate in scan.value.gates] == [
        f"{other_scene}-g01"
    ]


# ---------------------------------------------------------------------------
# 5. the discipline pins
# ---------------------------------------------------------------------------


def _all_constants(tree: ast.AST) -> list[str]:
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            found.append(node.value)
    return found


def _sql_constants(tree: ast.AST) -> list[str]:
    return [
        text
        for text in _all_constants(tree)
        if re.match(r"(?i)^\s*(select|insert|update|delete)\b", text)
    ]


def _function(tree: ast.AST, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"function {name!r} not found")


def test_the_pipeline_holds_no_transaction_and_spells_no_sql() -> None:
    """The contract's "零写权" made structural: the orchestrator's source
    carries no transaction-control constant, no SQL-shaped constant and
    no ``execute`` attribute call at all — every write it drives lands
    in a library face's own short transaction."""

    for text in _all_constants(PIPELINE_TREE):
        assert text not in {"BEGIN IMMEDIATE", "COMMIT", "ROLLBACK"}, text
    assert _sql_constants(PIPELINE_TREE) == []
    # the Gate-2 vocabulary, closed over the orchestrator: no DB-machinery
    # attribute call of any kind — not even a commit/rollback (the review's
    # F1: an "execute"-only scan let a self._conn.commit() / with-conn
    # mutation survive; the discipline word set now names them).
    for node in ast.walk(PIPELINE_TREE):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in {
                "execute",
                "executemany",
                "executescript",
                "commit",
                "rollback",
            }, ast.dump(node)


def test_the_creation_service_composes_the_arms_and_spells_no_dml() -> None:
    """``create_world_with_bible`` composes the stores' ``*_tx`` arms —
    it re-spells none of their SQL: the module carries no DML constant,
    its public face owns exactly one ``BEGIN IMMEDIATE`` … ``COMMIT``
    pair, and the five arms it calls are named in its body."""

    assert _sql_constants(BOOTSTRAP_TREE) == []
    public = _function(BOOTSTRAP_TREE, "create_world_with_bible")
    constants = _all_constants(public)
    assert constants.count("BEGIN IMMEDIATE") == 1
    assert constants.count("COMMIT") == 1
    called = {
        node.func.attr
        for node in ast.walk(public)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    for arm in (
        "_create_world_tx",
        "_seed_bible_tx",
        "_bind_actor_tx",
        "_seed_actor_profile_tx",
        "_seed_player_character_tx",
    ):
        assert arm in called, arm


def test_the_store_faces_keep_their_own_transaction_and_arms_open_none() -> None:
    """The V3-8a splits are behavior preserving: every public write face
    the creation service composes still owns exactly one
    ``BEGIN IMMEDIATE`` … ``COMMIT``; the new arms carry the SQL and no
    transaction control."""

    for tree, names in (
        (STORE_TREE, ("create_world", "bind_actor")),
        (BIBLE_TREE, ("seed_bible",)),
        (CAST_TREE, ("seed_actor_profile", "seed_player_character")),
    ):
        for name in names:
            constants = _all_constants(_function(tree, name))
            assert constants.count("BEGIN IMMEDIATE") == 1, name
            assert constants.count("COMMIT") == 1, name
    for tree, names in (
        (STORE_TREE, ("_create_world_tx", "_bind_actor_tx")),
        (BIBLE_TREE, ("_seed_bible_tx",)),
        (
            CAST_TREE,
            ("_seed_actor_profile_tx", "_seed_player_character_tx"),
        ),
    ):
        for name in names:
            arm = _function(tree, name)
            assert _sql_constants(arm), name
            for text in _all_constants(arm):
                assert text not in {
                    "BEGIN IMMEDIATE",
                    "COMMIT",
                    "ROLLBACK",
                }, name


def test_the_providers_module_is_a_leaf_and_holds_no_write_power() -> None:
    """The provider face at rest: no ``sqlite3`` import, no transaction
    constant, no SQL-shaped constant, no ``execute`` call — the module
    is a leaf whose elc imports are all annotation imports guarded by
    ``TYPE_CHECKING``."""

    names = {
        alias.name.split(".")[0]
        for node in ast.walk(PROVIDERS_TREE)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert "sqlite3" not in names
    all_imports = [
        node
        for node in ast.walk(PROVIDERS_TREE)
        if isinstance(node, ast.ImportFrom)
    ]
    guarded: list[ast.stmt] = []
    for node in ast.walk(PROVIDERS_TREE):
        if isinstance(node, ast.If):
            test = node.test
            if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
                guarded.extend(node.body)
    guarded_imports = [
        node for node in guarded if isinstance(node, ast.ImportFrom)
    ]
    elc_imports = [
        node for node in all_imports if (node.module or "").startswith("elc.")
    ]
    assert elc_imports, "the annotation imports themselves"
    assert set(map(id, elc_imports)) <= set(map(id, guarded_imports))
    for node in guarded_imports:
        assert (node.module or "").startswith("elc."), node.module
    stdlib = {
        node.module for node in all_imports if node not in elc_imports
    }
    assert stdlib <= {
        "__future__",
        "collections.abc",
        "dataclasses",
        "typing",
    }
    for text in _all_constants(PROVIDERS_TREE):
        assert text not in {"BEGIN IMMEDIATE", "COMMIT", "ROLLBACK"}
    assert _sql_constants(PROVIDERS_TREE) == []
    for node in ast.walk(PROVIDERS_TREE):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr != "execute"


def test_the_new_modules_are_not_re_exported_from_the_world_package() -> None:
    """The V3-1..V3-7 precedent: the new modules stay narrow — the
    package root does not re-export them."""

    source = (SRC_ROOT / "world" / "__init__.py").read_text(encoding="utf-8")
    for keyword in (
        "Pipeline",
        "DeterministicFakeProvider",
        "create_world_with_bible",
        "elc.world.pipeline",
        "elc.world.providers",
        "elc.world.bootstrap",
    ):
        assert keyword not in source, keyword


def test_the_new_modules_import_from_a_cold_interpreter() -> None:
    """The cold-start pin (the P4-3 discipline): the three new modules
    start clean in a fresh interpreter."""

    env = dict(
        os.environ,
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=str(REPO / "src"),
    )
    for module in (
        "elc.world.providers",
        "elc.world.bootstrap",
        "elc.world.pipeline",
    ):
        proc = subprocess.run(
            [sys.executable, "-c", f"import {module}"],
            cwd=REPO,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert proc.returncode == 0, (module, proc.stderr)


def test_the_ledger_carries_the_v3_8a_entries() -> None:
    """AOCI maintenance, pinned: the three new modules carry their own
    entries with the faces this cut owns, and the three touched store
    entries carry their new arms (the coverage law's sibling — the new
    modules have entries, and the touched ones name what moved)."""

    lines = AOCI_FILE.read_text(encoding="utf-8").split("\n")
    for tag, keywords in (
        (
            "pipeline.py[",
            ("Pipeline", "run_scene", "resume", "零写权"),
        ),
        (
            "providers.py[",
            (
                "DeterministicFakeProvider",
                "WriterProvider",
                "PlannerProvider",
                "ResolverProvider",
                "POV-safe",
            ),
        ),
        (
            "bootstrap.py[",
            ("create_world_with_bible", "全或无", "初始权威"),
        ),
    ):
        hits = [line for line in lines if line.startswith(tag)]
        assert len(hits) == 1, (tag, len(hits))
        for keyword in keywords:
            assert keyword in hits[0], (tag, keyword)
    world_section = "===D:/english-learning-clean/src/elc/world/==="
    start = next(
        index
        for index, line in enumerate(lines)
        if line.startswith(world_section)
    )
    end = next(
        index
        for index in range(start + 1, len(lines))
        if lines[index].startswith("===D:")
    )
    section = lines[start:end]
    for tag, keywords in (
        (
            "store.py[DB7T]",
            ("_create_world_tx", "_bind_actor_tx", "V3-8a"),
        ),
        ("bible.py[WB3M]", ("_seed_bible_tx", "V3-8a")),
        (
            "cast.py[WD9M]",
            (
                "_seed_actor_profile_tx",
                "_seed_player_character_tx",
                "V3-8a",
            ),
        ),
    ):
        hits = [line for line in section if line.startswith(tag)]
        assert len(hits) == 1, (tag, len(hits))
        for keyword in keywords:
            assert keyword in hits[0], (tag, keyword)
