"""V3-4 — the World Director + ``world_chapter(_plan)`` (the pin groups).

The Narrative V3 program's fourth cut (TASK-OPI-be7b094f…11 /
VAL-OPI-be7b094f…13; the ruling DEC-OPI-be7b094f…7): the
schema-and-table side of the Director — the strict Blueprint schema
(DATA §26.2.1's V3-4 block, the L3 landing), the durable cast-input
assembly (the V3-3R external review's item 5; the Package is a seed
source, never a runtime authority), the context read face, and the two
write faces that land a Blueprint as an adopted plan revision plus its
``world_scene`` position anchors. **Zero migration**: 0029's four
tables were V3-1's; this cut is pure code (the chain head stays
``0032_actor_profile_world_fk`` / ``32``). The #4 prerequisites (an
``ADOPTED`` Blueprint / Dossier before an activation; the overlap ban
covering a ``SETTLING`` chapter) turn on in this cut — group 4 pins
them at the store's own surface. The groups:

1. **schema pins** — the canonical key set word for word; a legal
   Blueprint passes with its supplemental keys riding verbatim; missing
   chapter/scene fields, wrong types, blank soft-expectation strings,
   and identities outside the durable namespace (the V3-3R negative
   controls: a persona id and a resident name both refuse) are all
   value-semantics refusals — never an exception;
2. **the durable cast-input assembly** — berrymoor seeded through the
   real open pass assembles exactly the two durable identities, Nell's
   profile six fields riding the member, the card-name join resolved,
   the player arm carrying only the profile face (the seed fields do
   not exist on the shape), the context carrying the Bible / storyline
   / CURRENT-fact arms — and the source scan: no package face is
   touched (no import, no SQL), plus the cold-start import pin;
3. **the write faces** — open_next_chapter's full chain (chapter
   PLANNED, plan ADOPTED, N PLANNED anchors, the derivation laws word
   for word), the store faces replaying the derived ids as no-ops (the
   idempotence rides the store's own creation faces), the chain moving
   forward one chapter per open, revise_blueprint's position-keyed diff
   (a new ordinal gets a row, a vanished still-PLANNED ordinal is
   discarded, a content change never touches an anchor, an ACTIVE
   anchor is never touched, a ``scene_index`` is never re-used) — and
   the refusals (dangling world / chapter, a bad payload writing
   nothing);
4. **the #4 prerequisites** (STATE §21/§22's 「V3-4 起强制」) — an
   ADOPTED Blueprint before a chapter opens, an ADOPTED Dossier before
   a scene activates, and the overlap ban covering an ACTIVE **or**
   SETTLING twin;
5. **Plan≠Canon** — opening and revising leave the canon face empty
   (the tick never moves, no chapter opens, every anchor's actual ticks
   stay null), the Director's own source carries no write SQL (the
   scan), and the legacy V2 surfaces' row counts never move;
6. **the chain head** — zero migration: the shared constants and the
   applied chain still end at 0032.
"""

from __future__ import annotations

import ast
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from elc.host import open_host
from elc.persona.provider import ScriptedPersonaProvider
from elc.platform.db.epoch import open_runtime_epoch
from elc.platform.db.migrations import apply_migrations
from elc.platform.types import DomainErrorCode, Err, Ok
from elc.world.bible import SqliteBibleStore
from elc.world.cast import SqliteCastStore, StoryRole
from elc.world.director import (
    BLUEPRINT_SCENE_KEYS,
    Director,
    build_cast_input,
    build_director_context,
    chapter_id_for,
    plan_id_for,
    scene_id_for,
    validate_blueprint,
)
from elc.world.narrative import (
    ChapterStatus,
    PlanRevisionStatus,
    SceneStatus,
    SqliteNarrativeStore,
)
from elc.world.package import BUILTIN_WORLDS_DIR, ensure_builtin_worlds
from elc.world.store import SqliteWorldStore
from elc.world.time import read_current_tick
from elc.world.types import WorldEvent
from tests.conftest import (
    MIGRATION_IDS,
    SCHEMA_HEAD_FILE,
    SCHEMA_HEAD_VERSION,
    SRC_ROOT,
)

REPO = Path(__file__).resolve().parents[2]

NOW = "2026-10-12T00:00:00+00:00"
LATER = "2026-10-12T01:00:00+00:00"

BERRYMOOR = "world-berrymoor"
TOWN = "world-town"

#: The two durable identities berrymoor's cast assembles into (the
#: V3-3R canonical identity): Nell's ``actor_id`` and the player's
#: ``player_character_id``.
BERRYMOOR_NAMESPACE = frozenset(
    {"actor-berrymoor-nell", "actor-berrymoor-you"}
)
TOWN_NAMESPACE = frozenset({"actor-lia", "pc-you"})

#: Nell's six profile words, verbatim from the shipped package (the
#: seed's source of truth — these ride the JSON as authored).
NELL_DRIVE = (
    "Keep the green door open on her own terms — the bindery working,"
    " her grandfather's tools staying hers, and the sign repainted"
    " rather than taken down."
)

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


def _seed_town(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    world_id: str = TOWN,
) -> None:
    """One hand-made world over the fresh database: the world row, one
    AI actor bound to a card, her seeded profile, and the reader's own
    durable character — the two durable identity sources the namespace
    assembles from (no package anywhere)."""

    created = world_store.create_world(world_id, "Town", None, NOW)
    assert isinstance(created, Ok)
    _insert_card(conn, "persona-lia", "Lia")
    _insert_actor(conn, "actor-lia", world_id, persona_id="persona-lia")
    seeded = cast_store.seed_actor_profile(
        "actor-lia",
        world_id,
        story_role=StoryRole.PROTAGONIST,
        pov_eligible=True,
        pov_weight=1,
        long_term_drive="keep the shop open a winter longer",
        now=NOW,
    )
    assert isinstance(seeded, Ok)
    player = cast_store.seed_player_character(
        "pc-you",
        world_id,
        name="You",
        background="a newcomer off the evening coach",
        location="the inn",
        state="tired",
        knowledge_refs="a rumour about the mill",
        now=NOW,
    )
    assert isinstance(player, Ok)


def _insert_card(
    conn: sqlite3.Connection, persona_id: str, name: str = "N"
) -> None:
    """One minimal character card (the card an actor binding needs —
    ``world_actor.persona_id`` rides the card table's own FK)."""

    conn.execute(
        "INSERT INTO character_card ("
        " character_id, persona_id, name, identity, personality,"
        " background, speech_style, \"values\", boundaries, opening,"
        " scenario, generation_policy, lore_refs, revision, status,"
        " is_builtin, created_at, updated_at"
        ") VALUES (?, ?, ?, 'i', 'p', 'b', 's', 'v', 'bo', 'o',"
        " 'sc', 'auto', '', 1, 'active', 1, ?, ?)",
        (f"cpkg-{persona_id}", persona_id, name, NOW, NOW),
    )


def _insert_actor(
    conn: sqlite3.Connection,
    actor_id: str,
    world_id: str,
    persona_id: str = "persona-lia",
) -> None:
    if persona_id != "persona-lia":
        _insert_card(conn, persona_id)
    conn.execute(
        "INSERT INTO world_actor (actor_id, world_id, persona_id,"
        " created_at) VALUES (?, ?, ?, ?)",
        (actor_id, world_id, persona_id, NOW),
    )
    # Committed at once: the store faces run their own
    # ``BEGIN IMMEDIATE`` transactions, and an open implicit
    # transaction would refuse them.
    conn.commit()


def _berrymoor_dir(tmp_path: Path) -> Path:
    """A temporary worlds directory carrying the shipped berrymoor
    package, byte for byte as it ships (the seed tests ride the real
    file's content through the real loader)."""

    directory = tmp_path / "worlds"
    directory.mkdir(exist_ok=True)
    (directory / "berrymoor.json").write_bytes(
        (BUILTIN_WORLDS_DIR / "berrymoor.json").read_bytes()
    )
    return directory


def _seed_berrymoor(
    tmp_path: Path,
) -> tuple[
    SqliteWorldStore,
    SqliteBibleStore,
    SqliteCastStore,
    SqliteNarrativeStore,
    sqlite3.Connection,
]:
    """Seed the shipped berrymoor through a temporary worlds directory
    over a fresh database — the real open pass seeds the world, its
    Bible, its cast and its storylines; the narrative store rides the
    same connection (the composition root's shape)."""

    directory = _berrymoor_dir(tmp_path)
    db = sqlite3.connect(str(tmp_path / "seed.db"))
    db.execute("PRAGMA foreign_keys=ON")
    apply_migrations(db)
    fence = open_runtime_epoch(db)
    world_store = SqliteWorldStore(db, fence)
    bible_store = SqliteBibleStore(db, fence)
    cast_store = SqliteCastStore(db, fence)
    ensure_builtin_worlds(
        world_store,
        directory,
        persona_exists=lambda persona_id: persona_id == "persona-nell-alder",
        bible_store=bible_store,
        cast_store=cast_store,
    )
    return (
        world_store,
        bible_store,
        cast_store,
        SqliteNarrativeStore(db, fence),
        db,
    )


def _director(
    db: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
) -> Director:
    return Director(
        db,
        world_store=world_store,
        cast_store=cast_store,
        bible_store=bible_store,
        narrative_store=narrative,
    )


def _scene(
    pov: str,
    participants: tuple[str, ...],
    purpose: str = "first sight",
    **extras: Any,
) -> dict[str, Any]:
    """One Blueprint scene draft — the canonical ten keys, plus whatever
    the Director's own keys the caller passes."""

    return {
        "purpose": purpose,
        "place": "the bindery steps",
        "pov_actor_id": pov,
        "participants": list(participants),
        "planned_start_tick": 0,
        "entry_goals": "greet the newcomer",
        "exit_condition": "the greeting lands or breaks",
        "elasticity": "may run long if you linger",
        "revealable": "the ledger's back page",
        "must_hide": "the priced tools",
        **extras,
    }


def _blueprint(
    pov: str = "actor-lia",
    you: str = "pc-you",
    scenes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """One Blueprint-shaped payload — the nine chapter fields, the
    soft-expectation set among them (the V3-0R wording law's own
    fields, never a postcondition)."""

    if scenes is None:
        scenes = [_scene(pov, (pov, you))]
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


def _add_adopted_plan(
    narrative: SqliteNarrativeStore, chapter_id: str, revision: int = 1
) -> None:
    """One plan revision landed and adopted through the store's own
    faces (the #4 prerequisite made true)."""

    plan_id = f"{chapter_id}-bp-r{revision}"
    created = narrative.create_plan(
        plan_id,
        chapter_id,
        revision,
        goal="g",
        dramatic_question="q",
        planned_start_tick=0,
        planned_end_tick=60,
        closing_pressure="p",
        desired_development="d",
        soft_outcomes="s",
        chapter_questions_to_advance="c",
        scenes=(),
        now=NOW,
    )
    assert isinstance(created, Ok)
    adopted = narrative.adopt_plan(plan_id, NOW, 1)
    assert isinstance(adopted, Ok)


def _activate_scene_with_dossier(
    narrative: SqliteNarrativeStore, scene_id: str
) -> None:
    """The #4 dance: a scene enters ACTIVE only through an adopted
    Dossier — create one, adopt it, then activate."""

    created = narrative.create_dossier(
        f"{scene_id}-d1",
        scene_id,
        1,
        pov_actor_id="actor-lia",
        participants=("actor-lia", "pc-you"),
        place="the shop",
        planned_start_tick=10,
        revealable="the ledger",
        must_hide="the debt",
        entry_goals="greet",
        exit_condition="the greeting lands",
        elasticity="may run long",
        now=NOW,
    )
    assert isinstance(created, Ok)
    adopted = narrative.adopt_dossier(f"{scene_id}-d1", NOW, 1)
    assert isinstance(adopted, Ok)
    activated = narrative.activate_scene(scene_id, NOW, 1)
    assert isinstance(activated, Ok)


def _row_counts(conn: sqlite3.Connection, tables: tuple[str, ...]) -> dict[str, int]:
    return {
        table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in tables
    }


# ---------------------------------------------------------------------------
# 1. schema pins
# ---------------------------------------------------------------------------


def test_the_canonical_scene_key_set_is_the_l3_list_word_for_word() -> None:
    """DATA §26.2.1's V3-4 block, key for key: the canonical ten are
    the ones the reconciliation and the Dossier both speak."""

    assert BLUEPRINT_SCENE_KEYS == (
        "purpose",
        "place",
        "pov_actor_id",
        "participants",
        "planned_start_tick",
        "entry_goals",
        "exit_condition",
        "elasticity",
        "revealable",
        "must_hide",
    )


def test_a_legal_blueprint_passes_and_the_extras_ride_verbatim() -> None:
    """The legal shape: every chapter field verbatim, the supplemental
    keys the Director grows (beats, gate hints) passed through
    unjudged into the returned records."""

    scene = _scene(
        "actor-lia",
        ("actor-lia", "pc-you"),
        beats=["the bell above the door"],
        gate_hint="ask about the sign",
    )
    payload = _blueprint(scenes=[scene])
    result = validate_blueprint(payload, namespace=TOWN_NAMESPACE)
    assert isinstance(result, Ok)
    blueprint = result.value
    assert blueprint.goal == payload["goal"]
    assert blueprint.dramatic_question == payload["dramatic_question"]
    assert blueprint.planned_start_tick == 0
    assert blueprint.planned_end_tick == 600
    assert blueprint.closing_pressure == payload["closing_pressure"]
    assert blueprint.desired_development == payload["desired_development"]
    assert blueprint.soft_outcomes == payload["soft_outcomes"]
    assert (
        blueprint.chapter_questions_to_advance
        == payload["chapter_questions_to_advance"]
    )
    assert blueprint.scenes == tuple(payload["scenes"])
    assert blueprint.scenes[0]["beats"] == ["the bell above the door"]
    assert blueprint.scenes[0]["gate_hint"] == "ask about the sign"


def test_missing_chapter_fields_are_refused_by_name() -> None:
    """The nine §26.2.1 chapter fields are all required — a missing one
    is refused ``VALIDATION_FAILED`` naming it."""

    for key in (
        "goal",
        "dramatic_question",
        "planned_start_tick",
        "planned_end_tick",
        "closing_pressure",
        "desired_development",
        "soft_outcomes",
        "chapter_questions_to_advance",
        "scenes",
    ):
        payload = _blueprint()
        del payload[key]
        result = validate_blueprint(payload, namespace=TOWN_NAMESPACE)
        assert isinstance(result, Err), key
        assert result.error.code is DomainErrorCode.VALIDATION_FAILED
        assert key in result.error.message, key


def test_wrong_chapter_field_types_are_refused() -> None:
    """A wrong type is refused — a bool is not a tick, a string is not
    a tick, a mapping is not a scene sequence."""

    for key, value in (
        ("goal", 7),
        ("dramatic_question", None),
        ("closing_pressure", ["a direction"]),
        ("soft_outcomes", 3),
        ("planned_start_tick", "0"),
        ("planned_start_tick", True),
        ("planned_end_tick", 1.5),
        ("scenes", "not a sequence"),
        ("scenes", {"1": "not a list"}),
    ):
        payload = _blueprint() | {key: value}
        result = validate_blueprint(payload, namespace=TOWN_NAMESPACE)
        assert isinstance(result, Err), (key, value)
        assert result.error.code is DomainErrorCode.VALIDATION_FAILED
        assert key in result.error.message, (key, value)


def test_blank_soft_expectations_are_refused() -> None:
    """The wording law's schema half (design §2.2): the four
    soft-expectation fields state a direction — an empty or blank one
    is refused, and the refusal says what the fields are not (a
    postcondition)."""

    for key in (
        "closing_pressure",
        "desired_development",
        "soft_outcomes",
        "chapter_questions_to_advance",
    ):
        for value in ("", "   "):
            payload = _blueprint() | {key: value}
            result = validate_blueprint(payload, namespace=TOWN_NAMESPACE)
            assert isinstance(result, Err), (key, value)
            assert result.error.code is DomainErrorCode.VALIDATION_FAILED
            assert key in result.error.message
            assert "postcondition" in result.error.message


def test_scene_elements_are_refused_key_by_key() -> None:
    """A scene element missing any canonical key, or carrying a wrong
    type, is refused in the blueprint's ordinal language
    (``scenes[1]`` — the coordinate the diff keys on)."""

    for key in BLUEPRINT_SCENE_KEYS:
        scene = _scene("actor-lia", ("actor-lia", "pc-you"))
        del scene[key]
        result = validate_blueprint(
            _blueprint(scenes=[scene]), namespace=TOWN_NAMESPACE
        )
        assert isinstance(result, Err), key
        assert result.error.code is DomainErrorCode.VALIDATION_FAILED
        assert key in result.error.message, key
        assert "scenes[1]" in result.error.message, key
    for key, value in (
        ("purpose", 1),
        ("place", None),
        ("entry_goals", []),
        ("exit_condition", 3),
        ("elasticity", {}),
        ("revealable", 2),
        ("must_hide", True),
        ("planned_start_tick", "10"),
        ("pov_actor_id", 5),
        ("participants", "actor-lia"),
    ):
        scene = _scene("actor-lia", ("actor-lia", "pc-you")) | {key: value}
        result = validate_blueprint(
            _blueprint(scenes=[scene]), namespace=TOWN_NAMESPACE
        )
        assert isinstance(result, Err), (key, value)
        assert result.error.code is DomainErrorCode.VALIDATION_FAILED
        assert key in result.error.message, (key, value)


def test_the_schema_face_keeps_the_v3_3r_identity_freeze() -> None:
    """The identity law: pov and participants speak the durable
    namespace only — a persona id (the CharacterCard / template
    identity) and a resident name (prose) are both refused, while the
    two durable identities pass."""

    for bad in ("persona-lia", "Old Tam", "actor-ghost"):
        pov_result = validate_blueprint(
            _blueprint(scenes=[_scene(bad, ("actor-lia", "pc-you"))]),
            namespace=TOWN_NAMESPACE,
        )
        assert isinstance(pov_result, Err), bad
        assert pov_result.error.code is DomainErrorCode.VALIDATION_FAILED
        assert bad in pov_result.error.message
        assert "canonical participant identity" in pov_result.error.message

        participants_result = validate_blueprint(
            _blueprint(
                scenes=[_scene("actor-lia", ("actor-lia", "pc-you", bad))]
            ),
            namespace=TOWN_NAMESPACE,
        )
        assert isinstance(participants_result, Err), bad
        assert participants_result.error.code is DomainErrorCode.VALIDATION_FAILED
        assert bad in participants_result.error.message

    legal = validate_blueprint(
        _blueprint(scenes=[_scene("actor-lia", ("actor-lia", "pc-you"))]),
        namespace=TOWN_NAMESPACE,
    )
    assert isinstance(legal, Ok)


def test_non_mappings_and_unencodable_extras_are_refused() -> None:
    """The shape refusals' outer ring: a payload that is not a mapping,
    an element that is not a mapping, and a supplemental value the plan
    row's JSON column cannot carry — all value-semantics refusals."""

    not_mapping = validate_blueprint(
        [("goal", "x")],  # type: ignore[arg-type]
        namespace=TOWN_NAMESPACE,
    )
    assert isinstance(not_mapping, Err)
    assert not_mapping.error.code is DomainErrorCode.VALIDATION_FAILED

    not_a_mapping_element = validate_blueprint(
        _blueprint(scenes=[_scene("actor-lia", ("actor-lia", "pc-you"))])
        | {"scenes": ["just a string"]},
        namespace=TOWN_NAMESPACE,
    )
    assert isinstance(not_a_mapping_element, Err)
    assert "scenes[1]" in not_a_mapping_element.error.message

    unencodable = validate_blueprint(
        _blueprint(
            scenes=[
                _scene(
                    "actor-lia",
                    ("actor-lia", "pc-you"),
                    beats={1, 2},
                )
            ]
        ),
        namespace=TOWN_NAMESPACE,
    )
    assert isinstance(unencodable, Err)
    assert unencodable.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "JSON-encodable" in unencodable.error.message


# ---------------------------------------------------------------------------
# 2. the durable cast-input assembly (the V3-3R item-5 recipe)
# ---------------------------------------------------------------------------


def test_the_cast_input_assembles_from_durable_instance_data(
    tmp_path: Path,
) -> None:
    """The real town: berrymoor seeded through the real open pass, the
    cast input assembled from durable rows alone — Nell's actor id and
    profile six fields, the card-name join, the player's own id, and
    the namespace exactly the two durable identities (the persona id
    and the resident names stay out — the freeze's negative
    controls)."""

    world_store, _bible_store, cast_store, _narrative, db = _seed_berrymoor(
        tmp_path
    )
    cast = build_cast_input(
        db, BERRYMOOR, world_store=world_store, cast_store=cast_store
    )
    assert [member.actor_id for member in cast.members] == [
        "actor-berrymoor-nell"
    ]
    nell = cast.members[0]
    assert nell.name == "Nell Alder"  # the character_card.name join
    assert nell.profile is not None
    assert nell.profile.story_role is StoryRole.PROTAGONIST
    assert nell.profile.pov_eligible is True
    assert nell.profile.pov_weight == 1
    assert nell.profile.long_term_drive == NELL_DRIVE
    assert nell.profile.current_arc_seed != ""
    assert nell.profile.private_context != ""
    assert cast.player_character is not None
    assert cast.player_character.player_character_id == "actor-berrymoor-you"
    assert cast.player_character.name == "你"
    assert (
        cast.player_character.background
        == "你是镇上的人，住在装订铺楼上的小房间"
    )
    assert cast.namespace == BERRYMOOR_NAMESPACE
    # The freeze's negative controls: the persona id (the
    # CharacterCard / template identity) and the residents' names (no
    # durable V3 participant identity) both stay out.
    assert "persona-nell-alder" not in cast.namespace
    assert "Old Tam" not in cast.namespace


def test_the_player_arm_carries_only_the_profile_face(
    tmp_path: Path,
) -> None:
    """The V3-3R seed freeze carried structurally: the Director's player
    shape has no ``location`` / ``state`` / ``knowledge_refs`` (their
    current authority is ``world_state_fact`` / V3-7's memory) and no
    unused档案 fields — a consumer cannot read the seed as a running
    fact through this arm by accident."""

    world_store, _bible_store, cast_store, _narrative, db = _seed_berrymoor(
        tmp_path
    )
    cast = build_cast_input(
        db, BERRYMOOR, world_store=world_store, cast_store=cast_store
    )
    player = cast.player_character
    assert player is not None
    for absent in (
        "location",
        "state",
        "knowledge_refs",
        "appearance",
        "abilities",
        "limits",
    ):
        assert not hasattr(player, absent), absent


def test_the_context_carries_the_named_arms(tmp_path: Path) -> None:
    """The context read face: the Bible revision, the cast input, the
    world's active storylines (the package's two opening arcs) and the
    CURRENT facts (empty on a freshly seeded town) — and the arms the
    contract has not granted yet (Chapter Summaries / Reader Exposure)
    do not exist on the shape."""

    world_store, bible_store, cast_store, _narrative, db = _seed_berrymoor(
        tmp_path
    )
    context = build_director_context(
        db,
        BERRYMOOR,
        world_store=world_store,
        cast_store=cast_store,
        bible_store=bible_store,
    )
    assert context.world_id == BERRYMOOR
    assert context.bible is not None
    assert context.bible.premise != ""
    assert len(context.storylines) == 2
    assert all(line.theme != "" for line in context.storylines)
    assert context.current_facts == ()
    assert context.cast.namespace == BERRYMOOR_NAMESPACE
    for absent in (
        "chapter_summaries",
        "summaries",
        "reader_exposure",
        "exposures",
    ):
        assert not hasattr(context, absent), absent


def test_the_name_join_falls_back_to_the_actor_id(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
) -> None:
    """The fallback law: a card the table names answers its name; a card
    named emptily falls back to the actor id — a plain signature, never
    a broken one (the web face's own fallback)."""

    _seed_town(conn, world_store, cast_store)
    _insert_card(conn, "persona-nameless", "")
    conn.execute(
        "INSERT INTO world_actor (actor_id, world_id, persona_id,"
        " created_at) VALUES (?, ?, ?, ?)",
        ("actor-nameless", TOWN, "persona-nameless", NOW),
    )
    conn.commit()
    cast = build_cast_input(
        conn, TOWN, world_store=world_store, cast_store=cast_store
    )
    names = {member.actor_id: member.name for member in cast.members}
    assert names == {
        "actor-lia": "Lia",
        "actor-nameless": "actor-nameless",
    }


def test_the_production_open_assembles_the_same_cast_input(
    tmp_path: Path,
) -> None:
    """The composition root's path: an ``open_host`` pass seeds the real
    builtin world, and the same assembly answers the same two durable
    identities — the recipe needs no package face at runtime."""

    host = open_host(tmp_path / "app.db", provider=ScriptedPersonaProvider())
    try:
        fence = open_runtime_epoch(host.db)
        cast = build_cast_input(
            host.db,
            BERRYMOOR,
            world_store=SqliteWorldStore(host.db, fence),
            cast_store=SqliteCastStore(host.db, fence),
        )
        assert cast.namespace == BERRYMOOR_NAMESPACE
        assert cast.player_character is not None
        assert cast.player_character.player_character_id == "actor-berrymoor-you"
        assert [member.actor_id for member in cast.members] == [
            "actor-berrymoor-nell"
        ]
    finally:
        host.close()


# ---------------------------------------------------------------------------
# the source scans (the write faces' own SQL; the package negative)
# ---------------------------------------------------------------------------

_DIRECTOR_SOURCE = (SRC_ROOT / "world" / "director.py").read_text(
    encoding="utf-8"
)
_DIRECTOR_TREE = ast.parse(_DIRECTOR_SOURCE, filename="director.py")


def _sql_statements() -> list[str]:
    """Every SQL-shaped string constant in the director module — a
    constant that *starts* with a DML keyword (the v3_1 scan's手法,
    narrowed to the leading keyword so prose that merely mentions a
    word cannot false-positive)."""

    found: list[str] = []
    for node in ast.walk(_DIRECTOR_TREE):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if re.match(r"(?i)^\s*(select|insert|update|delete)\b", node.value):
                found.append(node.value)
    return found


def test_the_assembly_source_never_reads_the_package() -> None:
    """The V3-3R item-5 negative, machine-checked: the director module
    imports no package face and no SQL of its own names one — the cast
    input is constructible from durable instance data alone."""

    statements = _sql_statements()
    assert statements, "the director carries no SQL at all — wrong source?"
    for text in statements:
        assert "package" not in text.lower(), text
    for node in ast.walk(_DIRECTOR_TREE):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("elc.world.package")
        elif isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith("elc.world.package")


def test_the_director_carries_no_write_sql_of_its_own() -> None:
    """The Plan≠Canon machine half: every SQL statement in the director
    module is a SELECT, and none of them names a narrative table — the
    four 0029 tables are written and read through
    :class:`SqliteNarrativeStore`'s own face and nowhere else."""

    statements = _sql_statements()
    assert statements
    for text in statements:
        assert re.match(r"(?i)^\s*select\b", text), text
        for table in (
            "world_chapter",
            "world_scene",
            "world_chapter_plan",
            "world_scene_dossier",
        ):
            assert table not in text, (table, text)


def test_the_director_module_imports_from_a_cold_interpreter() -> None:
    """The cold-start pin (the P4-3 discipline): a fresh interpreter
    importing the new module first must succeed; no import cycle may
    hide behind a lucky test-session order."""

    env = dict(
        os.environ,
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=str(REPO / "src"),
    )
    proc = subprocess.run(
        [sys.executable, "-c", "import elc.world.director"],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr


# ---------------------------------------------------------------------------
# 3. the write faces
# ---------------------------------------------------------------------------


def test_open_next_chapter_lands_the_full_chain(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    narrative: SqliteNarrativeStore,
    director: Director,
) -> None:
    """One open: the chapter minted ``PLANNED``, plan revision 1
    ``ADOPTED`` with every field verbatim, and one ``PLANNED`` anchor
    per scene element under the derivation laws — and the chapter is
    not opened (``ACTIVE`` is the lifecycle face's) while the tick does
    not move."""

    _seed_town(conn, world_store, cast_store)
    payload = _blueprint(
        scenes=[
            _scene("actor-lia", ("actor-lia", "pc-you")),
            _scene("actor-lia", ("actor-lia", "pc-you"), purpose="the ledger"),
        ]
    )
    opened = director.open_next_chapter(TOWN, payload, NOW)
    assert isinstance(opened, Ok)
    opening = opened.value
    assert opening.chapter.chapter_id == "world-town-ch01"
    assert opening.chapter.world_id == TOWN
    assert opening.chapter.chapter_index == 1
    assert opening.chapter.status is ChapterStatus.PLANNED
    assert opening.chapter.opened_at_tick is None
    assert opening.chapter.closed_at_tick is None
    assert opening.plan.chapter_plan_id == "world-town-ch01-bp-r1"
    assert opening.plan.plan_revision == 1
    assert opening.plan.status is PlanRevisionStatus.ADOPTED
    assert opening.plan.goal == payload["goal"]
    assert opening.plan.dramatic_question == payload["dramatic_question"]
    assert opening.plan.planned_start_tick == 0
    assert opening.plan.planned_end_tick == 600
    assert opening.plan.closing_pressure == payload["closing_pressure"]
    assert opening.plan.desired_development == payload["desired_development"]
    assert opening.plan.soft_outcomes == payload["soft_outcomes"]
    assert (
        opening.plan.chapter_questions_to_advance
        == payload["chapter_questions_to_advance"]
    )
    assert opening.plan.scenes == tuple(payload["scenes"])
    assert [row.scene_id for row in opening.scenes] == [
        "world-town-ch01-s01",
        "world-town-ch01-s02",
    ]
    assert [row.scene_index for row in opening.scenes] == [1, 2]
    assert all(row.status is SceneStatus.PLANNED for row in opening.scenes)
    assert all(
        row.actual_start_tick is None and row.actual_end_tick is None
        for row in opening.scenes
    )
    # The Plan face is in; the canon face is empty; the tick has not
    # moved (the Director has no write path to it — N-INV-007).
    assert narrative.adopted_plan("world-town-ch01") is not None
    assert narrative.active_chapter(TOWN) is None
    tick = read_current_tick(conn, TOWN)
    assert isinstance(tick, Ok)
    assert tick.value == 0


def test_the_derivation_laws_are_the_l3_spelling() -> None:
    """The three id laws, word for word (the L3 block): zero-padded
    chapter and scene ordinals, the unpadded plan revision."""

    assert chapter_id_for("world-berrymoor", 1) == "world-berrymoor-ch01"
    assert chapter_id_for("world-berrymoor", 12) == "world-berrymoor-ch12"
    assert plan_id_for("world-berrymoor-ch01", 1) == "world-berrymoor-ch01-bp-r1"
    assert plan_id_for("world-berrymoor-ch01", 12) == "world-berrymoor-ch01-bp-r12"
    assert scene_id_for("world-berrymoor-ch01", 1) == "world-berrymoor-ch01-s01"
    assert scene_id_for("world-berrymoor-ch01", 12) == "world-berrymoor-ch01-s12"


def test_the_store_faces_replay_the_derived_ids_without_new_rows(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    narrative: SqliteNarrativeStore,
    director: Director,
) -> None:
    """The replay law, at the level where it is true (「经 store 幂等性
    自然达成」): the derived ids of one open replayed through the
    store's own creation faces answer the stored rows — nothing new is
    written, row counts and the records' state_versions ride
    unchanged."""

    _seed_town(conn, world_store, cast_store)
    payload = _blueprint(
        scenes=[
            _scene("actor-lia", ("actor-lia", "pc-you")),
            _scene("actor-lia", ("actor-lia", "pc-you"), purpose="the ledger"),
        ]
    )
    opened = director.open_next_chapter(TOWN, payload, NOW)
    assert isinstance(opened, Ok)
    opening = opened.value
    tables = ("world_chapter", "world_chapter_plan", "world_scene")
    before = _row_counts(conn, tables)
    assert before == {
        "world_chapter": 1,
        "world_chapter_plan": 1,
        "world_scene": 2,
    }

    validated = director.validate_blueprint(TOWN, payload)
    assert isinstance(validated, Ok)
    blueprint = validated.value
    replayed_chapter = narrative.create_chapter("world-town-ch01", TOWN, 1, LATER)
    assert isinstance(replayed_chapter, Ok)
    assert replayed_chapter.value == opening.chapter
    replayed_plan = narrative.create_plan(
        "world-town-ch01-bp-r1",
        "world-town-ch01",
        1,
        goal=blueprint.goal,
        dramatic_question=blueprint.dramatic_question,
        planned_start_tick=blueprint.planned_start_tick,
        planned_end_tick=blueprint.planned_end_tick,
        closing_pressure=blueprint.closing_pressure,
        desired_development=blueprint.desired_development,
        soft_outcomes=blueprint.soft_outcomes,
        chapter_questions_to_advance=blueprint.chapter_questions_to_advance,
        scenes=blueprint.scenes,
        now=LATER,
    )
    assert isinstance(replayed_plan, Ok)
    assert replayed_plan.value == opening.plan
    for index, row in enumerate(opening.scenes, start=1):
        replayed_scene = narrative.create_scene(
            row.scene_id, "world-town-ch01", index, LATER
        )
        assert isinstance(replayed_scene, Ok)
        assert replayed_scene.value == row
    assert _row_counts(conn, tables) == before

    # And the Director itself moves the chain forward one chapter per
    # call (§21's monotone +1): the next open derives the next ids.
    second = director.open_next_chapter(TOWN, payload, LATER)
    assert isinstance(second, Ok)
    assert second.value.chapter.chapter_id == "world-town-ch02"
    assert second.value.chapter.chapter_index == 2
    assert second.value.plan.chapter_plan_id == "world-town-ch02-bp-r1"
    assert [row.scene_id for row in second.value.scenes] == [
        "world-town-ch02-s01",
        "world-town-ch02-s02",
    ]
    assert len(narrative.chapters_of(TOWN)) == 2


def test_open_next_chapter_refuses_a_dangling_world_and_a_bad_payload(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    narrative: SqliteNarrativeStore,
    director: Director,
) -> None:
    """A world that does not exist is ``NOT_FOUND``; a payload that
    fails the schema is ``VALIDATION_FAILED`` **before anything is
    written** — a refused open leaves no chapter row behind."""

    refused = director.open_next_chapter("world-nowhere", _blueprint(), NOW)
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.NOT_FOUND
    assert "world-nowhere" in refused.error.message

    _seed_town(conn, world_store, cast_store)
    bad = _blueprint() | {"closing_pressure": ""}
    refused_payload = director.open_next_chapter(TOWN, bad, NOW)
    assert isinstance(refused_payload, Err)
    assert refused_payload.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "closing_pressure" in refused_payload.error.message
    assert narrative.chapters_of(TOWN) == ()


def test_revise_blueprint_diffs_by_position(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    narrative: SqliteNarrativeStore,
    director: Director,
) -> None:
    """The L3 Diff rules, position-keyed: a new revision is appended and
    adopted (the old one superseded); a vanished ordinal's still-PLANNED
    row is discarded; a surviving ordinal's row is never touched even
    when the element's content changed; a new ordinal gets a new
    ``PLANNED`` row; and a retired ``scene_index`` is never re-used
    (one anchor per index, its retired word riding it)."""

    _seed_town(conn, world_store, cast_store)
    scenes = [
        _scene("actor-lia", ("actor-lia", "pc-you"), purpose=f"beat {i}")
        for i in (1, 2, 3)
    ]
    opened = director.open_next_chapter(TOWN, _blueprint(scenes=scenes), NOW)
    assert isinstance(opened, Ok)
    _activate_scene_with_dossier(narrative, "world-town-ch01-s02")

    # Revision 2: two elements, the first reworded — the anchors of the
    # surviving positions do not move (a row is a progress anchor, the
    # JSON is the content source); the vanished position 3 is
    # discarded.
    revised = director.revise_blueprint(
        "world-town-ch01",
        _blueprint(
            scenes=[
                _scene(
                    "actor-lia",
                    ("actor-lia", "pc-you"),
                    purpose="a different first sight",
                ),
                _scene("actor-lia", ("actor-lia", "pc-you"), purpose="beat 2"),
            ]
        ),
        LATER,
    )
    assert isinstance(revised, Ok)
    assert revised.value.plan.chapter_plan_id == "world-town-ch01-bp-r2"
    assert revised.value.plan.plan_revision == 2
    assert revised.value.plan.status is PlanRevisionStatus.ADOPTED
    first_revision = narrative.get_plan("world-town-ch01-bp-r1")
    assert first_revision is not None
    assert first_revision.status is PlanRevisionStatus.SUPERSEDED
    rows = {row.scene_index: row for row in narrative.scenes_of("world-town-ch01")}
    assert set(rows) == {1, 2, 3}
    assert rows[1].status is SceneStatus.PLANNED
    assert rows[1].state_version == 1  # content change never touches it
    assert rows[2].status is SceneStatus.ACTIVE
    assert rows[2].state_version == 2  # the dossier dance's activation
    assert rows[3].status is SceneStatus.DISCARDED
    assert rows[3].state_version == 2  # mint + discard

    # Revision 3: four elements — position 4 is new (a new PLANNED
    # row); position 3 stays the one discarded anchor (a scene_index is
    # never re-used: the retired index is not re-minted).
    revised_three = director.revise_blueprint(
        "world-town-ch01",
        _blueprint(
            scenes=[
                _scene("actor-lia", ("actor-lia", "pc-you")),
                _scene("actor-lia", ("actor-lia", "pc-you"), purpose="beat 2"),
                _scene("actor-lia", ("actor-lia", "pc-you"), purpose="beat 3"),
                _scene("actor-lia", ("actor-lia", "pc-you"), purpose="beat 4"),
            ]
        ),
        LATER,
    )
    assert isinstance(revised_three, Ok)
    assert revised_three.value.plan.plan_revision == 3
    rows = {row.scene_index: row for row in narrative.scenes_of("world-town-ch01")}
    assert set(rows) == {1, 2, 3, 4}
    assert rows[4].scene_id == "world-town-ch01-s04"
    assert rows[4].status is SceneStatus.PLANNED
    assert rows[4].state_version == 1
    assert rows[3].scene_id == "world-town-ch01-s03"
    assert rows[3].status is SceneStatus.DISCARDED  # the retired anchor stays
    assert [
        plan.status for plan in narrative.plans_of("world-town-ch01")
    ] == [
        PlanRevisionStatus.SUPERSEDED,
        PlanRevisionStatus.SUPERSEDED,
        PlanRevisionStatus.ADOPTED,
    ]


def test_revise_blueprint_never_touches_an_active_anchor(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    narrative: SqliteNarrativeStore,
    director: Director,
) -> None:
    """N-INV-003 at the diff: a vanished ordinal whose anchor is ACTIVE
    (the world has touched it) is **never touched** by a replanning,
    while a still-PLANNED vanished ordinal is discarded — and the
    chapter row itself carries no plan work (its state_version does not
    move)."""

    _seed_town(conn, world_store, cast_store)
    scenes = [
        _scene("actor-lia", ("actor-lia", "pc-you"), purpose=f"beat {i}")
        for i in (1, 2, 3, 4)
    ]
    opened = director.open_next_chapter(TOWN, _blueprint(scenes=scenes), NOW)
    assert isinstance(opened, Ok)
    _activate_scene_with_dossier(narrative, "world-town-ch01-s02")

    revised = director.revise_blueprint(
        "world-town-ch01",
        _blueprint(
            scenes=[_scene("actor-lia", ("actor-lia", "pc-you"))]
        ),
        LATER,
    )
    assert isinstance(revised, Ok)
    rows = {row.scene_index: row for row in narrative.scenes_of("world-town-ch01")}
    assert rows[1].status is SceneStatus.PLANNED
    assert rows[2].status is SceneStatus.ACTIVE  # never un-happened
    assert rows[2].state_version == 2
    assert rows[3].status is SceneStatus.DISCARDED
    assert rows[3].state_version == 2
    assert rows[4].status is SceneStatus.DISCARDED
    assert rows[4].state_version == 2
    chapter = narrative.get_chapter("world-town-ch01")
    assert chapter is not None
    assert chapter.state_version == 1  # the plan face is not the chapter face
    assert narrative.adopted_plan("world-town-ch01") is not None
    adopted = narrative.adopted_plan("world-town-ch01")
    assert adopted is not None
    assert adopted.plan_revision == 2


def test_revise_blueprint_refuses_a_dangling_chapter_and_a_bad_payload(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    narrative: SqliteNarrativeStore,
    director: Director,
) -> None:
    """The revise refusals: a chapter that does not exist is
    ``NOT_FOUND``; a payload that fails the schema is
    ``VALIDATION_FAILED`` before anything is written (no plan revision
    lands), and an empty scene list is a legal Blueprint — no hidden
    non-emptiness law lives in the schema."""

    refused = director.revise_blueprint("chapter-ghost", _blueprint(), NOW)
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.NOT_FOUND

    _seed_town(conn, world_store, cast_store)
    opened = director.open_next_chapter(TOWN, _blueprint(), NOW)
    assert isinstance(opened, Ok)
    bad = _blueprint() | {"scenes": "nope"}
    refused_payload = director.revise_blueprint("world-town-ch01", bad, LATER)
    assert isinstance(refused_payload, Err)
    assert refused_payload.error.code is DomainErrorCode.VALIDATION_FAILED
    assert len(narrative.plans_of("world-town-ch01")) == 1

    empty_scenes = director.revise_blueprint(
        "world-town-ch01", _blueprint(scenes=[]), LATER
    )
    assert isinstance(empty_scenes, Ok)
    assert empty_scenes.value.plan.scenes == ()
    assert [
        row.status for row in narrative.scenes_of("world-town-ch01")
    ] == [SceneStatus.DISCARDED]


# ---------------------------------------------------------------------------
# 4. the #4 prerequisites (STATE §21/§22, 「V3-4 起强制」)
# ---------------------------------------------------------------------------


def test_a_chapter_opens_only_with_an_adopted_blueprint(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    narrative: SqliteNarrativeStore,
) -> None:
    """The chapter's #4 prerequisite: a ``PLANNED`` chapter with no
    ``ADOPTED`` plan revision refuses to open — ``VALIDATION_FAILED``,
    the message naming the missing Blueprint, the refusal releasing
    nothing — and the same chapter opens once the plan is adopted."""

    _seed_town(conn, world_store, cast_store)
    created = narrative.create_chapter("world-town-ch01", TOWN, 1, NOW)
    assert isinstance(created, Ok)
    refused = narrative.activate_chapter(
        "world-town-ch01", 0, NOW, expected_state_version=1
    )
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "ADOPTED Blueprint" in refused.error.message
    still = narrative.get_chapter("world-town-ch01")
    assert still is not None
    assert still.status is ChapterStatus.PLANNED
    assert still.state_version == 1

    _add_adopted_plan(narrative, "world-town-ch01")
    opened = narrative.activate_chapter(
        "world-town-ch01", 0, NOW, expected_state_version=1
    )
    assert isinstance(opened, Ok)
    assert opened.value.status is ChapterStatus.ACTIVE
    assert opened.value.opened_at_tick == 0


def test_a_scene_activates_only_with_an_adopted_dossier(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    narrative: SqliteNarrativeStore,
) -> None:
    """The scene's #4 prerequisite: a ``PLANNED`` scene with no
    ``ADOPTED`` dossier revision refuses to activate — the message
    naming the missing Dossier — and the same scene activates once the
    dossier is adopted (the actual ticks still untouched: the commit
    cuts own them)."""

    _seed_town(conn, world_store, cast_store)
    created = narrative.create_chapter("world-town-ch01", TOWN, 1, NOW)
    assert isinstance(created, Ok)
    seeded = narrative.create_scene("world-town-ch01-s01", "world-town-ch01", 1, NOW)
    assert isinstance(seeded, Ok)
    refused = narrative.activate_scene(
        "world-town-ch01-s01", NOW, expected_state_version=1
    )
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "ADOPTED Dossier" in refused.error.message
    still = narrative.get_scene("world-town-ch01-s01")
    assert still is not None
    assert still.status is SceneStatus.PLANNED
    assert still.state_version == 1

    _activate_scene_with_dossier(narrative, "world-town-ch01-s01")
    activated = narrative.get_scene("world-town-ch01-s01")
    assert activated is not None
    assert activated.status is SceneStatus.ACTIVE
    assert activated.actual_start_tick is None
    assert activated.actual_end_tick is None


def test_the_overlap_ban_covers_active_and_settling_chapters(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    narrative: SqliteNarrativeStore,
) -> None:
    """The #4 overlap extension: with both chapters' Blueprints adopted,
    a world holding an ACTIVE chapter refuses the next opening, and —
    since V3-4 — a **SETTLING** chapter refuses it too (the message
    naming the sleeping twin); only after the previous chapter closes
    does the next one open."""

    _seed_town(conn, world_store, cast_store)
    for index in (1, 2):
        created = narrative.create_chapter(
            f"world-town-ch{index:02d}", TOWN, index, NOW
        )
        assert isinstance(created, Ok)
        _add_adopted_plan(narrative, f"world-town-ch{index:02d}")

    opened = narrative.activate_chapter(
        "world-town-ch01", 0, NOW, expected_state_version=1
    )
    assert isinstance(opened, Ok)
    refused_active = narrative.activate_chapter(
        "world-town-ch02", 0, NOW, expected_state_version=1
    )
    assert isinstance(refused_active, Err)
    assert refused_active.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "world-town-ch01" in refused_active.error.message
    assert "ACTIVE" in refused_active.error.message
    assert "one chapter at a time" in refused_active.error.message

    settled = narrative.settle_chapter(
        "world-town-ch01", now=LATER, expected_state_version=2
    )
    assert isinstance(settled, Ok)
    assert settled.value.status is ChapterStatus.SETTLING
    refused_settling = narrative.activate_chapter(
        "world-town-ch02", 0, NOW, expected_state_version=1
    )
    assert isinstance(refused_settling, Err)
    assert refused_settling.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "SETTLING" in refused_settling.error.message
    assert "world-town-ch01" in refused_settling.error.message
    still = narrative.get_chapter("world-town-ch02")
    assert still is not None
    assert still.status is ChapterStatus.PLANNED
    assert still.state_version == 1

    closed = narrative.close_chapter(
        "world-town-ch01", closed_at_tick=90, now=LATER, expected_state_version=3
    )
    assert isinstance(closed, Ok)
    opened_two = narrative.activate_chapter(
        "world-town-ch02", 90, NOW, expected_state_version=1
    )
    assert isinstance(opened_two, Ok)
    assert opened_two.value.status is ChapterStatus.ACTIVE


# ---------------------------------------------------------------------------
# 5. Plan≠Canon (the cut's pin) and the V2 chain
# ---------------------------------------------------------------------------


def test_opening_and_revising_leave_the_canon_face_empty(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    narrative: SqliteNarrativeStore,
    director: Director,
) -> None:
    """Plan≠Canon, read off the tables: after an open and a revision the
    world still reads zero canon progress — no chapter opens, every
    anchor's actual ticks stay null, the tick reads 0 — while the Plan
    face carries the newest adopted revision."""

    _seed_town(conn, world_store, cast_store)
    opened = director.open_next_chapter(
        TOWN,
        _blueprint(
            scenes=[
                _scene("actor-lia", ("actor-lia", "pc-you")),
                _scene("actor-lia", ("actor-lia", "pc-you"), purpose="the ledger"),
            ]
        ),
        NOW,
    )
    assert isinstance(opened, Ok)
    revised = director.revise_blueprint(
        "world-town-ch01",
        _blueprint(scenes=[_scene("actor-lia", ("actor-lia", "pc-you"))]),
        LATER,
    )
    assert isinstance(revised, Ok)

    tick = read_current_tick(conn, TOWN)
    assert isinstance(tick, Ok)
    assert tick.value == 0
    chapter = narrative.get_chapter("world-town-ch01")
    assert chapter is not None
    assert chapter.status is ChapterStatus.PLANNED
    assert chapter.opened_at_tick is None
    assert chapter.closed_at_tick is None
    assert narrative.active_chapter(TOWN) is None
    rows = narrative.scenes_of("world-town-ch01")
    assert [row.status for row in rows] == [
        SceneStatus.PLANNED,
        SceneStatus.DISCARDED,
    ]
    assert all(
        row.actual_start_tick is None and row.actual_end_tick is None
        for row in rows
    )
    adopted = narrative.adopted_plan("world-town-ch01")
    assert adopted is not None
    assert adopted.plan_revision == 2


def test_the_v2_surfaces_are_untouched(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    narrative: SqliteNarrativeStore,
    director: Director,
) -> None:
    """N-R-INV-008's two-chains law at the Director: a full V3-4
    activity (open, revise, both activations) writes nothing into
    ``world_run`` / ``world_reveal_item`` / ``world_event``, and the V2
    store's own writes still land alongside."""

    _seed_town(conn, world_store, cast_store)
    event = world_store.record_event(
        WorldEvent(
            event_id="event-v2-1",
            world_id=TOWN,
            kind="beat",
            narration="the mill wheel turns",
            effects=(),
            occurred_at=NOW,
            source="test",
        )
    )
    assert isinstance(event, Ok)
    tables = ("world_run", "world_reveal_item", "world_event")
    before = _row_counts(conn, tables)
    assert before == {
        "world_run": 0,
        "world_reveal_item": 0,
        "world_event": 1,
    }

    opened = director.open_next_chapter(TOWN, _blueprint(), NOW)
    assert isinstance(opened, Ok)
    revised = director.revise_blueprint(
        "world-town-ch01",
        _blueprint(
            scenes=[
                _scene("actor-lia", ("actor-lia", "pc-you")),
                _scene("actor-lia", ("actor-lia", "pc-you"), purpose="next"),
            ]
        ),
        LATER,
    )
    assert isinstance(revised, Ok)
    assert isinstance(
        narrative.activate_chapter(
            "world-town-ch01", 0, NOW, expected_state_version=1
        ),
        Ok,
    )
    _activate_scene_with_dossier(narrative, "world-town-ch01-s01")

    assert _row_counts(conn, tables) == before
    chronicle = world_store.chronicle_of(TOWN)
    assert isinstance(chronicle, Ok)
    assert chronicle.value is not None
    assert [row.event_id for row in chronicle.value] == ["event-v2-1"]
    # The V2 store's own writes still land alongside the V3 activity.
    followup = world_store.record_event(
        WorldEvent(
            event_id="event-v2-2",
            world_id=TOWN,
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
# 6. the chain head (zero migration)
# ---------------------------------------------------------------------------


def test_the_chain_head_did_not_move() -> None:
    """Zero migration: the shared constants and the applied chain still
    end at 0032 — this cut is pure code over V3-1's four tables."""

    assert MIGRATION_IDS[-1] == "0032_actor_profile_world_fk"
    assert SCHEMA_HEAD_FILE == "0032_actor_profile_world_fk.sql"
    assert SCHEMA_HEAD_VERSION == "32"
    assert not any(name.startswith("0033") for name in MIGRATION_IDS)
