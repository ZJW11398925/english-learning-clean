"""V3-4 — the World Director + ``world_chapter(_plan)`` (the pin groups);
revised by V3-4R (TASK-OPI-be7b094f…23 / DEC-OPI-be7b094f…21).

The Narrative V3 program's fourth cut (TASK-OPI-be7b094f…11 /
VAL-OPI-be7b094f…13; the ruling DEC-OPI-be7b094f…7): the
schema-and-table side of the Director — the strict Blueprint schema
(DATA §26.2.1's V3-4 block, the L3 landing), the durable cast-input
assembly (the V3-3R external review's item 5; the Package is a seed
source, never a runtime authority), the context read face, and the two
write faces that land a Blueprint as an adopted plan revision plus its
``world_scene`` identity anchors. **Zero migration**: 0029's four
tables were V3-1's; this cut is pure code (the chain head then ended at
``0032_actor_profile_world_fk`` / ``32`` — V3-5's
``0033_segment_commit`` and V3-5R's ``0034_segment_terminality`` moved
it afterwards, and group 6 speaks the
live lineage). The #4 prerequisites (an
``ADOPTED`` Blueprint / Dossier before an activation; the overlap ban
covering a ``SETTLING`` chapter) turn on in this cut — group 4 pins
them at the store's own surface.

The V3-4R correction (the external review's five items) lands here:
**scene identity separates from presentation order** (``scene_ref`` /
burned ``scene_id`` / unused-monotonic minting; retired anchors never
revived — the HIGH), **world authority is fail-closed** (no ``CURRENT``
Bible, no planning) and the context carries the **canonical tick**,
**POV eligibility is authority** (``pov_eligible`` False / undeclared
both refuse; the POV must be among the participants) and the cast
input thickens (six card person fields / three player profile fields),
plus the tightening laws (non-empty ``scenes``; ordered chapter window;
scene ticks inside it). The groups:

1. **schema pins** — the canonical key set word for word; a legal
   Blueprint passes with its supplemental keys riding verbatim; missing
   chapter/scene fields, wrong types, blank soft-expectation strings,
   the V3-4R tightening (empty ``scenes`` / reversed chapter window /
   scene ticks outside it), the identity pair's payload-local checks
   (type / agreement / duplicate) and identities outside the durable
   namespace (the V3-3R negative controls: a persona id and a resident
   name both refuse) are all value-semantics refusals — never an
   exception; POV eligibility and the POV-in-participants invariant
   are pinned against explicit authority maps;
2. **the durable cast-input assembly** — berrymoor seeded through the
   real open pass assembles exactly the two durable identities, Nell's
   profile six fields riding the member, the card join resolved wide
   (name + six person fields; a card-less member still stands with six
   empty strings), the player arm carrying the profile face (three
   new fields ride; the seed fields do not exist on the shape), the
   context carrying the Bible / storyline / CURRENT-fact arms plus the
   canonical tick — and the source scan: no package face is touched
   (no import, no SQL), plus the cold-start import pin;
3. **the write faces** — open_next_chapter's full chain (chapter
   PLANNED, plan ADOPTED, identity stamping byte for byte, N PLANNED
   anchors, the derivation laws word for word), the store faces
   replaying the landed shapes as no-ops, the chain moving forward one
   chapter per open, revise_blueprint's identity-keyed diff (refs keep
   their anchors, a content change never touches a row, a fresh
   element mints ``max + 1``, a vanished still-PLANNED anchor is
   discarded, an ACTIVE anchor is never touched, a ``scene_index`` is
   never re-used, no ghost rows) — the five ``scene_ref`` refusals,
   the read-back law (a burned identity is never rewritten, a
   disagreeing pair refuses) and the refusals (dangling world /
   chapter, a bad payload writing nothing, an authority-less world);
4. **the #4 prerequisites** (STATE §21/§22's 「V3-4 起强制」) — an
   ADOPTED Blueprint before a chapter opens, an ADOPTED Dossier before
   a scene activates, and the overlap ban covering an ACTIVE **or**
   SETTLING twin;
5. **Plan≠Canon** — opening and revising leave the canon face empty
   (the tick never moves, no chapter opens, every anchor's actual ticks
   stay null), the Director's own source carries no write SQL (the
   scan), and the legacy V2 surfaces' row counts never move;
6. **the chain head** — this cut added no migration; the shared
   constants and the applied chain then ended at 0032 (V3-5's
   ``0033_segment_commit`` and V3-5R's ``0034_segment_terminality``
   moved them afterwards, and the pin speaks
   the live lineage).
"""

from __future__ import annotations

import ast
import os
import re
import sqlite3
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from elc.host import open_host
from elc.persona.provider import ScriptedPersonaProvider
from elc.platform.db.epoch import open_runtime_epoch
from elc.platform.db.migrations import apply_migrations
from elc.platform.types import DomainErrorCode, Err, Ok, Result
from elc.world.bible import BibleContent, SqliteBibleStore
from elc.world.cast import SqliteCastStore, StoryRole
from elc.world.director import (
    BLUEPRINT_SCENE_KEYS,
    ChapterBlueprint,
    Director,
    _next_unused_scene_index,
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
    encode_scenes,
)
from elc.world.package import BUILTIN_WORLDS_DIR, ensure_builtin_worlds
from elc.world.store import SqliteWorldStore
from elc.world.time import advance_current_tick, read_current_tick
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
    *,
    with_bible: bool = True,
) -> None:
    """One hand-made world over the fresh database: the world row, one
    AI actor bound to a card, her seeded profile (``pov_eligible =
    True`` — the V3-4R POV authority the schema face reads), the
    reader's own durable character, and — unless the caller asks
    otherwise — the world's ``CURRENT`` Bible revision (the fail-closed
    law's world authority, seeded through the Bible store's own face;
    ``with_bible=False`` seeds an authority-less world for that law's
    own pin)."""

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
    if with_bible:
        bible_store = SqliteBibleStore(conn, open_runtime_epoch(conn))
        seeded_bible = bible_store.seed_bible(
            f"{world_id}-bible-r1",
            world_id,
            BibleContent(premise="the town by the water"),
            NOW,
        )
        assert isinstance(seeded_bible, Ok)


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


def _validate(
    payload: Mapping[str, Any],
    *,
    player_character_id: str | None = "pc-you",
    pov_eligibility: Mapping[str, bool | None] | None = None,
) -> Result[ChapterBlueprint]:
    """The schema face over the town's own authority: the namespace, the
    player id and the one actor's declared eligibility — the same three
    answers ``Director.validate_blueprint`` assembles from the durable
    cast input, spelled here so the schema pins can vary one of them at
    a time."""

    return validate_blueprint(
        payload,
        namespace=TOWN_NAMESPACE,
        player_character_id=player_character_id,
        pov_eligibility=(
            {"actor-lia": True} if pov_eligibility is None else pov_eligibility
        ),
    )


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
    result = _validate(payload)
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
        result = _validate(payload)
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
        result = _validate(payload)
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
            result = _validate(payload)
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
        result = _validate(_blueprint(scenes=[scene]))
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
        result = _validate(_blueprint(scenes=[scene]))
        assert isinstance(result, Err), (key, value)
        assert result.error.code is DomainErrorCode.VALIDATION_FAILED
        assert key in result.error.message, (key, value)


def test_the_schema_face_keeps_the_v3_3r_identity_freeze() -> None:
    """The identity law: pov and participants speak the durable
    namespace only — a persona id (the CharacterCard / template
    identity) and a resident name (prose) are both refused, while the
    two durable identities pass."""

    for bad in ("persona-lia", "Old Tam", "actor-ghost"):
        pov_result = _validate(
            _blueprint(scenes=[_scene(bad, ("actor-lia", "pc-you"))])
        )
        assert isinstance(pov_result, Err), bad
        assert pov_result.error.code is DomainErrorCode.VALIDATION_FAILED
        assert bad in pov_result.error.message
        assert "canonical participant identity" in pov_result.error.message

        participants_result = _validate(
            _blueprint(
                scenes=[_scene("actor-lia", ("actor-lia", "pc-you", bad))]
            )
        )
        assert isinstance(participants_result, Err), bad
        assert participants_result.error.code is DomainErrorCode.VALIDATION_FAILED
        assert bad in participants_result.error.message

    legal = _validate(
        _blueprint(scenes=[_scene("actor-lia", ("actor-lia", "pc-you"))])
    )
    assert isinstance(legal, Ok)


def test_non_mappings_and_unencodable_extras_are_refused() -> None:
    """The shape refusals' outer ring: a payload that is not a mapping,
    an element that is not a mapping, and a supplemental value the plan
    row's JSON column cannot carry — all value-semantics refusals."""

    not_mapping = validate_blueprint(
        [("goal", "x")],  # type: ignore[arg-type]
        namespace=TOWN_NAMESPACE,
        player_character_id="pc-you",
        pov_eligibility={"actor-lia": True},
    )
    assert isinstance(not_mapping, Err)
    assert not_mapping.error.code is DomainErrorCode.VALIDATION_FAILED

    not_a_mapping_element = _validate(
        _blueprint(scenes=[_scene("actor-lia", ("actor-lia", "pc-you"))])
        | {"scenes": ["just a string"]}
    )
    assert isinstance(not_a_mapping_element, Err)
    assert "scenes[1]" in not_a_mapping_element.error.message

    unencodable = _validate(
        _blueprint(
            scenes=[
                _scene(
                    "actor-lia",
                    ("actor-lia", "pc-you"),
                    beats={1, 2},
                )
            ]
        )
    )
    assert isinstance(unencodable, Err)
    assert unencodable.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "JSON-encodable" in unencodable.error.message


def test_the_v3_4r_tightening_laws_hold() -> None:
    """The V3-4R minimal semantics tightening: ``scenes`` is non-empty;
    the chapter window never runs backwards; a scene's
    ``planned_start_tick`` is non-negative and never starts past the
    chapter's ``planned_end_tick`` — while a tick exactly at the
    chapter's end is legal (the message speaks the ordinal language)."""

    empty = _validate(_blueprint() | {"scenes": []})
    assert isinstance(empty, Err)
    assert empty.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "scenes" in empty.error.message

    reversed_window = _validate(_blueprint() | {"planned_start_tick": 601})
    assert isinstance(reversed_window, Err)
    assert reversed_window.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "planned_start_tick" in reversed_window.error.message
    assert "planned_end_tick" in reversed_window.error.message

    negative = _validate(
        _blueprint()
        | {
            "scenes": [
                _scene("actor-lia", ("actor-lia", "pc-you"))
                | {"planned_start_tick": -1}
            ]
        }
    )
    assert isinstance(negative, Err)
    assert negative.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "scenes[1]" in negative.error.message
    assert "negative" in negative.error.message

    beyond = _validate(
        _blueprint()
        | {
            "scenes": [
                _scene("actor-lia", ("actor-lia", "pc-you"))
                | {"planned_start_tick": 601}
            ]
        }
    )
    assert isinstance(beyond, Err)
    assert beyond.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "scenes[1]" in beyond.error.message
    assert "planned_end_tick" in beyond.error.message

    at_the_edge = _validate(
        _blueprint()
        | {
            "scenes": [
                _scene("actor-lia", ("actor-lia", "pc-you"))
                | {"planned_start_tick": 600}
            ]
        }
    )
    assert isinstance(at_the_edge, Ok)  # == planned_end_tick is inside


def test_the_identity_pair_is_checked_payload_locally() -> None:
    """The ``scene_ref`` / ``scene_id`` pair's payload-local half (the
    V3-4R identity model): ``scene_ref`` is an integer, strictly (a
    ``bool`` and a string both refuse); ``scene_id`` is a string; both
    present must agree on the index; and two elements may not declare
    one identity — whether through ``scene_ref`` or through a burned
    ``scene_id`` (the anchored half lives in the resolution; see the
    write-face refusals below)."""

    base = _blueprint()
    for bad_ref in (True, "1", 1.0, None):
        result = _validate(
            base
            | {
                "scenes": [
                    _scene("actor-lia", ("actor-lia", "pc-you"))
                    | {"scene_ref": bad_ref}
                ]
            }
        )
        assert isinstance(result, Err), bad_ref
        assert result.error.code is DomainErrorCode.VALIDATION_FAILED
        assert "scene_ref" in result.error.message, bad_ref

    bad_id = _validate(
        base
        | {
            "scenes": [
                _scene("actor-lia", ("actor-lia", "pc-you"))
                | {"scene_id": 7}
            ]
        }
    )
    assert isinstance(bad_id, Err)
    assert "scene_id" in bad_id.error.message

    disagreeing = _validate(
        base
        | {
            "scenes": [
                _scene("actor-lia", ("actor-lia", "pc-you"))
                | {"scene_ref": 1, "scene_id": "world-town-ch01-s02"}
            ]
        }
    )
    assert isinstance(disagreeing, Err)
    assert disagreeing.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "must agree" in disagreeing.error.message

    # A well-formed pair passes the payload-local half (the resolution
    # judges whether the anchor exists — group 3's pins).
    agreeing = _validate(
        _blueprint(
            scenes=[
                _scene("actor-lia", ("actor-lia", "pc-you"))
                | {"scene_ref": 2, "scene_id": "world-town-ch07-s02"}
            ]
        )
    )
    assert isinstance(agreeing, Ok)

    duplicate_refs = _validate(
        _blueprint(
            scenes=[
                _scene("actor-lia", ("actor-lia", "pc-you"))
                | {"scene_ref": 1},
                _scene("actor-lia", ("actor-lia", "pc-you"))
                | {"scene_ref": 1},
            ]
        )
    )
    assert isinstance(duplicate_refs, Err)
    assert duplicate_refs.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "scene_ref" in duplicate_refs.error.message

    mixed_identity = _validate(
        _blueprint(
            scenes=[
                _scene("actor-lia", ("actor-lia", "pc-you"))
                | {"scene_ref": 1},
                _scene("actor-lia", ("actor-lia", "pc-you"))
                | {"scene_id": "world-town-ch01-s01"},
            ]
        )
    )
    assert isinstance(mixed_identity, Err)
    assert "repeats the anchor identity 1" in mixed_identity.error.message


def test_pov_eligibility_is_authority_not_decoration() -> None:
    """The V3-4R review's item 3 at the schema face: an AI actor with
    an explicit ``False`` is refused (the message naming
    ``pov_eligible``); an undeclared eligibility — ``None`` on the
    profile, or no profile row at all — is refused too (undeclared is
    not automatically authorized); the declared ``True`` actor and the
    ``player_character_id`` both pass."""

    declared = _scene("actor-lia", ("actor-lia", "pc-you"))
    refused_false = _validate(
        _blueprint(scenes=[declared]), pov_eligibility={"actor-lia": False}
    )
    assert isinstance(refused_false, Err)
    assert refused_false.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "pov_eligible" in refused_false.error.message

    refused_none = _validate(
        _blueprint(scenes=[declared]), pov_eligibility={"actor-lia": None}
    )
    assert isinstance(refused_none, Err)
    assert refused_none.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "pov_eligible" in refused_none.error.message

    refused_missing = _validate(_blueprint(scenes=[declared]), pov_eligibility={})
    assert isinstance(refused_missing, Err)
    assert "pov_eligible" in refused_missing.error.message

    passed = _validate(_blueprint(scenes=[declared]))
    assert isinstance(passed, Ok)

    player_pov = _validate(
        _blueprint(
            scenes=[_scene("pc-you", ("pc-you", "actor-lia"))]
        ),
        pov_eligibility={},
    )
    assert isinstance(player_pov, Ok)


def test_the_pov_must_be_among_the_participants() -> None:
    """The V3-4R schema invariant: a POV absent from her own scene's
    ``participants`` is refused — for the reader's character exactly as
    for an AI actor (even one the authority declares eligible)."""

    actor_absent = _validate(
        _blueprint(scenes=[_scene("actor-lia", ("pc-you",))])
    )
    assert isinstance(actor_absent, Err)
    assert actor_absent.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "participants" in actor_absent.error.message
    assert "actor-lia" in actor_absent.error.message

    player_absent = _validate(
        _blueprint(scenes=[_scene("pc-you", ("actor-lia",))])
    )
    assert isinstance(player_absent, Err)
    assert player_absent.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "participants" in player_absent.error.message


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
    # The V3-4R card thickening: the six person fields ride from the
    # shipped character_card row (the builtin Nell declares all six).
    assert "bookbinder" in nell.identity
    assert nell.personality != ""
    assert nell.background != ""
    assert nell.speech_style != ""
    assert nell.values != ""
    assert nell.boundaries != ""
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


def test_the_player_arm_carries_the_profile_face_only(
    tmp_path: Path,
) -> None:
    """The V3-3R seed freeze carried structurally, thickened by V3-4R:
    the Director's player shape carries the character's档案 three more
    fields (``appearance`` / ``abilities`` / ``limits`` — the V3-4R
    review's item 3) and still has no ``location`` / ``state`` /
    ``knowledge_refs`` (their current authority is ``world_state_fact``
    / V3-7's memory) — a consumer cannot read the creation-time seed as
    a running fact through this arm by accident."""

    world_store, _bible_store, cast_store, _narrative, db = _seed_berrymoor(
        tmp_path
    )
    cast = build_cast_input(
        db, BERRYMOOR, world_store=world_store, cast_store=cast_store
    )
    player = cast.player_character
    assert player is not None
    for present in ("appearance", "abilities", "limits"):
        assert hasattr(player, present), present
    for absent in ("location", "state", "knowledge_refs"):
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
    assert context.current_tick == 0  # the seed world starts at tick zero
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
        assert cast.members[0].identity != ""
    finally:
        host.close()


def test_a_cardless_member_still_assembles_with_empty_faces(
    tmp_path: Path,
) -> None:
    """The honest-undeclared arm of the V3-4R card thickening: a member
    whose card the join cannot reach still stands — the name falls back
    to the actor id and the six person fields ride the empty string,
    never a guessed value (the FK-on profile normally guarantees a card;
    this defensive arm covers **corruption / a future cascade risk** —
    a binding outliving its card is refused today by the deletion
    programme's RESTRICT posture and unreachable under foreign-key
    enforcement, which is exactly why the reader carries the arm; the
    C1-c corrupted-state precedent's honest framing). Constructed
    FK-off: the state is unreachable under foreign-key enforcement."""

    db = sqlite3.connect(tmp_path / "cardless.db")  # FK off by default
    apply_migrations(db)
    fence = open_runtime_epoch(db)
    world_store = SqliteWorldStore(db, fence)
    cast_store = SqliteCastStore(db, fence)
    created = world_store.create_world(TOWN, "Town", None, NOW)
    assert isinstance(created, Ok)
    db.execute(
        "INSERT INTO world_actor (actor_id, world_id, persona_id,"
        " created_at) VALUES (?, ?, ?, ?)",
        ("actor-drifter", TOWN, "persona-gone", NOW),
    )
    db.commit()

    cast = build_cast_input(
        db, TOWN, world_store=world_store, cast_store=cast_store
    )
    assert [member.actor_id for member in cast.members] == ["actor-drifter"]
    drifter = cast.members[0]
    assert drifter.name == "actor-drifter"  # the fallback signature
    for face in (
        "identity",
        "personality",
        "background",
        "speech_style",
        "values",
        "boundaries",
    ):
        assert getattr(drifter, face) == "", face
    assert drifter.profile is None


def test_the_context_tick_reads_the_canonical_story_time(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    director: Director,
) -> None:
    """The V3-4R review's item 2 at the context face: ``current_tick``
    reads the world's canonical story time — zero on a seeded world,
    and the moved value after the tick primitive advances (the
    Director only *reads* it here; advancing is the commit
    transactions' move, N-INV-007)."""

    _seed_town(conn, world_store, cast_store)
    context = director.context(TOWN)
    assert context.current_tick == 0

    advanced = advance_current_tick(conn, TOWN, 7)
    assert isinstance(advanced, Ok)
    assert advanced.value == 7
    conn.commit()

    context = director.context(TOWN)
    assert context.current_tick == 7


def test_the_bound_schema_face_reads_the_cast_authority(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    director: Director,
) -> None:
    """The bound face's wiring (MH-2 at the instance, not the map): the
    eligibility comes from the world's own ``world_actor_profile`` rows
    — a declared-``False`` actor and a profile-less actor are both
    refused (the latter with the same undeclared sentence), the
    ``True`` actor passes, and the player character passes outright."""

    _seed_town(conn, world_store, cast_store)
    _insert_actor(conn, "actor-refuser", TOWN, persona_id="persona-refuser")
    refused_profile = cast_store.seed_actor_profile(
        "actor-refuser",
        TOWN,
        story_role=StoryRole.SUPPORTING,
        pov_eligible=False,
        now=NOW,
    )
    assert isinstance(refused_profile, Ok)
    _insert_actor(conn, "actor-mute", TOWN, persona_id="persona-mute")
    # No profile at all for actor-mute — the honest undeclared.

    declined = director.validate_blueprint(
        TOWN,
        _blueprint(
            scenes=[_scene("actor-refuser", ("actor-refuser", "pc-you"))]
        ),
    )
    assert isinstance(declined, Err)
    assert declined.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "pov_eligible" in declined.error.message

    undeclared = director.validate_blueprint(
        TOWN,
        _blueprint(scenes=[_scene("actor-mute", ("actor-mute", "pc-you"))]),
    )
    assert isinstance(undeclared, Err)
    assert undeclared.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "pov_eligible" in undeclared.error.message

    declared = director.validate_blueprint(
        TOWN,
        _blueprint(scenes=[_scene("actor-lia", ("actor-lia", "pc-you"))]),
    )
    assert isinstance(declared, Ok)

    player = director.validate_blueprint(
        TOWN,
        _blueprint(scenes=[_scene("pc-you", ("pc-you", "actor-lia"))]),
    )
    assert isinstance(player, Ok)


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


def test_the_reconciler_mints_no_positional_range_anchors() -> None:
    """The V3-4R spine (the HIGH's regression guard): no ``range`` call
    survives anywhere in the director module — anchor indexes are never
    minted from array ordinals — and the one minting law is
    ``max(existing) + 1``, pinned by behaviour on the module's own
    function."""

    for node in ast.walk(_DIRECTOR_TREE):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id != "range", ast.dump(node)

    assert _next_unused_scene_index([]) == 1
    assert _next_unused_scene_index([1, 2, 3]) == 4
    assert _next_unused_scene_index([3]) == 4  # gaps are not reused


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
    # The V3-4R identity stamping: every fresh element carries its
    # derived scene_id (the one added key — see the byte-level pin
    # below).
    assert opening.plan.scenes == tuple(
        {**element, "scene_id": f"world-town-ch01-s{index:02d}"}
        for index, element in enumerate(payload["scenes"], start=1)
    )
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


def test_open_stamps_the_burned_scene_id_without_touching_other_bytes(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    director: Director,
) -> None:
    """Identity stamping, byte for byte (the V3-4R HIGH): the plan row's
    ``scenes`` JSON differs from the caller's table by exactly one added
    key per element (``scene_id``, appended) — every other key and value
    byte-identical, under the store's own deterministic codec."""

    _seed_town(conn, world_store, cast_store)
    payload = _blueprint(
        scenes=[
            _scene("actor-lia", ("actor-lia", "pc-you"), purpose="one"),
            _scene(
                "actor-lia",
                ("actor-lia", "pc-you"),
                purpose="two",
                beats=["the bell above the door"],
            ),
        ]
    )
    opened = director.open_next_chapter(TOWN, payload, NOW)
    assert isinstance(opened, Ok)

    expected = tuple(
        {**element, "scene_id": f"world-town-ch01-s{index:02d}"}
        for index, element in enumerate(payload["scenes"], start=1)
    )
    assert opened.value.plan.scenes == expected
    raw = conn.execute(
        "SELECT scenes FROM world_chapter_plan WHERE chapter_plan_id = ?",
        ("world-town-ch01-bp-r1",),
    ).fetchone()[0]
    assert raw == encode_scenes(expected)
    for given, stored in zip(payload["scenes"], expected, strict=True):
        assert set(stored) - set(given) == {"scene_id"}
        assert {
            key: value for key, value in stored.items() if key != "scene_id"
        } == given
        # The burned key is appended, so the original key order is the
        # byte order the caller gave.
        assert list(stored)[:-1] == list(given)


def test_the_store_faces_replay_the_derived_ids_without_new_rows(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    narrative: SqliteNarrativeStore,
    director: Director,
) -> None:
    """The replay law, at the level where it is true (「经 store 幂等性
    自然达成」): the landed shapes of one open replayed through the
    store's own creation faces answer the stored rows — nothing new is
    written, row counts and the records' state_versions ride unchanged.
    Since V3-4R the landed plan's scenes table *is* the stamped one
    (identity stamping happens before the row lands), so the replay
    speaks those bytes — the same id with the same shape."""

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

    replayed_chapter = narrative.create_chapter("world-town-ch01", TOWN, 1, LATER)
    assert isinstance(replayed_chapter, Ok)
    assert replayed_chapter.value == opening.chapter
    replayed_plan = narrative.create_plan(
        opening.plan.chapter_plan_id,
        opening.plan.chapter_id,
        opening.plan.plan_revision,
        goal=opening.plan.goal,
        dramatic_question=opening.plan.dramatic_question,
        planned_start_tick=opening.plan.planned_start_tick,
        planned_end_tick=opening.plan.planned_end_tick,
        closing_pressure=opening.plan.closing_pressure,
        desired_development=opening.plan.desired_development,
        soft_outcomes=opening.plan.soft_outcomes,
        chapter_questions_to_advance=(
            opening.plan.chapter_questions_to_advance
        ),
        scenes=opening.plan.scenes,
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


def test_open_next_chapter_refuses_a_reference_before_anything_is_written(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    narrative: SqliteNarrativeStore,
    director: Director,
) -> None:
    """The V3-4R review's F6: the open face's own declaration — a
    ``scene_ref`` / burned ``scene_id`` that names no anchor of the
    (brand-new) chapter is refused **before a single write**: the error
    names the reference and the chapter, and the world holds zero
    chapter rows afterwards."""

    _seed_town(conn, world_store, cast_store)
    refused = director.open_next_chapter(
        TOWN,
        _blueprint(
            scenes=[_scene("actor-lia", ("actor-lia", "pc-you"), scene_ref=1)]
        ),
        NOW,
    )
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "scene_ref" in refused.error.message
    assert "world-town-ch01" in refused.error.message
    assert narrative.chapters_of(TOWN) == ()


def test_the_context_read_fails_fast_for_a_dangling_world(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
) -> None:
    """The V3-4R review's F3: the context read's declared precondition —
    ``build_director_context`` reads ``world.current_tick`` and a world
    the table does not know raises ``ValueError`` naming it (the store
    family's bad-row posture, declared in the docstring)."""

    with pytest.raises(ValueError, match="world-nowhere"):
        build_director_context(
            conn,
            "world-nowhere",
            world_store=world_store,
            cast_store=cast_store,
            bible_store=bible_store,
        )


def test_revise_blueprint_diffs_by_position(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    narrative: SqliteNarrativeStore,
    director: Director,
) -> None:
    """The L3 Diff rules' positional half: a new revision is appended
    and adopted (the old one superseded); a surviving ordinal's row is
    never touched even when the element's content changed (the row is a
    progress anchor, the JSON is the content source); a vanished
    ordinal's still-PLANNED row is discarded; and the retired index
    keeps its anchor (never re-used, never re-minted). The identity
    references (``scene_ref`` / burned ``scene_id``) and the fresh
    minting law have their own pins below."""

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
    assert rows[1].scene_id == "world-town-ch01-s01"  # the same anchor
    assert [
        plan.status for plan in narrative.plans_of("world-town-ch01")
    ] == [
        PlanRevisionStatus.SUPERSEDED,
        PlanRevisionStatus.ADOPTED,
    ]


def test_the_identity_model_keeps_anchors_across_revisions(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    narrative: SqliteNarrativeStore,
    director: Director,
) -> None:
    """The V3-4R e2e (the review's own acceptance shape): rev1 =
    [s1, s2, s3] → rev2 = [ref s01, ref s02] (s03 DISCARDED) → rev3 =
    [ref s01, ref s02, {fresh}] ⇒ the fresh scene mints **s04**
    (``scene_index = 4``, PLANNED — ``max(existing) + 1`` over a
    retired index), the retired s03 stays retired, no ghost row exists
    (rows = elements + retired), and s04 walks the whole dossier dance
    to ACTIVE."""

    _seed_town(conn, world_store, cast_store)
    opened = director.open_next_chapter(
        TOWN,
        _blueprint(
            scenes=[
                _scene("actor-lia", ("actor-lia", "pc-you"), purpose=f"beat {i}")
                for i in (1, 2, 3)
            ]
        ),
        NOW,
    )
    assert isinstance(opened, Ok)

    revised = director.revise_blueprint(
        "world-town-ch01",
        _blueprint(
            scenes=[
                _scene(
                    "actor-lia",
                    ("actor-lia", "pc-you"),
                    purpose="a different first sight",
                    scene_ref=1,
                ),
                _scene(
                    "actor-lia", ("actor-lia", "pc-you"), purpose="beat 2",
                    scene_ref=2,
                ),
            ]
        ),
        LATER,
    )
    assert isinstance(revised, Ok)
    rows = {row.scene_index: row for row in narrative.scenes_of("world-town-ch01")}
    assert set(rows) == {1, 2, 3}
    assert rows[1].status is SceneStatus.PLANNED
    assert rows[1].state_version == 1  # ref keeps the anchor; content moved
    assert rows[1].scene_id == "world-town-ch01-s01"
    assert rows[2].scene_id == "world-town-ch01-s02"
    assert rows[3].status is SceneStatus.DISCARDED

    revised_three = director.revise_blueprint(
        "world-town-ch01",
        _blueprint(
            scenes=[
                _scene(
                    "actor-lia", ("actor-lia", "pc-you"), purpose="beat 1 v3",
                    scene_ref=1,
                ),
                _scene(
                    "actor-lia", ("actor-lia", "pc-you"), purpose="beat 2",
                    scene_ref=2,
                ),
                _scene(
                    "actor-lia", ("actor-lia", "pc-you"), purpose="the fresh scene"
                ),
            ]
        ),
        LATER,
    )
    assert isinstance(revised_three, Ok)
    rows = {row.scene_index: row for row in narrative.scenes_of("world-town-ch01")}
    assert set(rows) == {1, 2, 3, 4}  # 3 elements + 1 retired: no ghost
    assert rows[4].scene_id == "world-town-ch01-s04"
    assert rows[4].status is SceneStatus.PLANNED
    assert rows[4].state_version == 1
    assert rows[3].status is SceneStatus.DISCARDED  # retired forever
    assert revised_three.value.plan.scenes[2]["scene_id"] == (
        "world-town-ch01-s04"
    )
    assert [
        plan.status for plan in narrative.plans_of("world-town-ch01")
    ] == [
        PlanRevisionStatus.SUPERSEDED,
        PlanRevisionStatus.SUPERSEDED,
        PlanRevisionStatus.ADOPTED,
    ]

    # The fresh anchor is a normal planned scene: the dossier dance
    # carries it to ACTIVE (the #4 prerequisite included).
    _activate_scene_with_dossier(narrative, "world-town-ch01-s04")
    fresh = narrative.get_scene("world-town-ch01-s04")
    assert fresh is not None
    assert fresh.status is SceneStatus.ACTIVE
    assert fresh.actual_start_tick is None  # the commits own the actuals


def test_scene_refs_refuse_the_five_ways(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    narrative: SqliteNarrativeStore,
    director: Director,
) -> None:
    """The ``scene_ref`` refusals, one arm each (the V3-4R HIGH): a
    duplicate ref; a ref naming no anchor of this chapter; another
    chapter's index (addressable only in its own chapter); a
    ``DISCARDED`` anchor (retired forever); and the position conflict
    (a ref whose array ordinal is already occupied by another anchor).
    Every one a value-semantics ``VALIDATION_FAILED`` writing nothing —
    the plan-revision count never moves."""

    _seed_town(conn, world_store, cast_store)
    opened = director.open_next_chapter(
        TOWN,
        _blueprint(
            scenes=[
                _scene("actor-lia", ("actor-lia", "pc-you"), purpose=f"beat {i}")
                for i in (1, 2, 3)
            ]
        ),
        NOW,
    )
    assert isinstance(opened, Ok)

    duplicate = director.revise_blueprint(
        "world-town-ch01",
        _blueprint(
            scenes=[
                _scene("actor-lia", ("actor-lia", "pc-you"), scene_ref=1),
                _scene("actor-lia", ("actor-lia", "pc-you"), scene_ref=1),
            ]
        ),
        LATER,
    )
    assert isinstance(duplicate, Err)
    assert duplicate.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "scene_ref" in duplicate.error.message

    nowhere = director.revise_blueprint(
        "world-town-ch01",
        _blueprint(
            scenes=[_scene("actor-lia", ("actor-lia", "pc-you"), scene_ref=9)]
        ),
        LATER,
    )
    assert isinstance(nowhere, Err)
    assert nowhere.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "names no anchor" in nowhere.error.message
    assert "world-town-ch01" in nowhere.error.message

    # Another chapter's index is no identity here: ch01 holds anchor 1,
    # ch02 (hand-made, no anchors) referencing 1 still refuses.
    made = narrative.create_chapter("world-town-ch02", TOWN, 2, NOW)
    assert isinstance(made, Ok)
    foreign = director.revise_blueprint(
        "world-town-ch02",
        _blueprint(
            scenes=[_scene("actor-lia", ("actor-lia", "pc-you"), scene_ref=1)]
        ),
        LATER,
    )
    assert isinstance(foreign, Err)
    assert foreign.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "names no anchor" in foreign.error.message
    assert "world-town-ch02" in foreign.error.message

    conflict = director.revise_blueprint(
        "world-town-ch01",
        _blueprint(
            scenes=[_scene("actor-lia", ("actor-lia", "pc-you"), scene_ref=2)]
        ),
        LATER,
    )
    assert isinstance(conflict, Err)
    assert conflict.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "conflicts" in conflict.error.message

    discarded = director.revise_blueprint(
        "world-town-ch01",
        _blueprint(
            scenes=[
                _scene("actor-lia", ("actor-lia", "pc-you"), scene_ref=1),
                _scene("actor-lia", ("actor-lia", "pc-you"), scene_ref=2),
            ]
        ),
        LATER,
    )
    assert isinstance(discarded, Ok)  # s03 retires here
    retired = director.revise_blueprint(
        "world-town-ch01",
        _blueprint(
            scenes=[
                _scene("actor-lia", ("actor-lia", "pc-you"), scene_ref=1),
                _scene("actor-lia", ("actor-lia", "pc-you"), scene_ref=2),
                _scene("actor-lia", ("actor-lia", "pc-you"), scene_ref=3),
            ]
        ),
        LATER,
    )
    assert isinstance(retired, Err)
    assert retired.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "DISCARDED" in retired.error.message

    # Nothing was written by the four refusals: two revisions only (the
    # open's and the retiring revise), three anchors with their words
    # intact.
    assert len(narrative.plans_of("world-town-ch01")) == 2
    rows = {row.scene_index: row for row in narrative.scenes_of("world-town-ch01")}
    assert set(rows) == {1, 2, 3}
    assert rows[3].status is SceneStatus.DISCARDED


def test_a_revision_never_rewrites_a_burned_identity(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    narrative: SqliteNarrativeStore,
    director: Director,
) -> None:
    """The read-back law: a stamped element resubmitted (``scene_id``
    alone, no ``scene_ref``) resolves by its burned identity, the new
    revision carries the same ``scene_id`` for the same anchors, the
    dropped tail anchor retires, and the earlier revision's column
    bytes stay byte for byte what the open wrote — a burned identity is
    never rewritten."""

    _seed_town(conn, world_store, cast_store)
    opened = director.open_next_chapter(
        TOWN,
        _blueprint(
            scenes=[
                _scene("actor-lia", ("actor-lia", "pc-you"), purpose=f"beat {i}")
                for i in (1, 2, 3)
            ]
        ),
        NOW,
    )
    assert isinstance(opened, Ok)
    read_back = opened.value.plan.scenes
    assert all("scene_id" in element for element in read_back)

    revised = director.revise_blueprint(
        "world-town-ch01",
        _blueprint(scenes=[read_back[0], read_back[1]]),
        LATER,
    )
    assert isinstance(revised, Ok)
    assert revised.value.plan.scenes[0]["scene_id"] == read_back[0]["scene_id"]
    assert revised.value.plan.scenes[1]["scene_id"] == read_back[1]["scene_id"]
    rows = {row.scene_index: row for row in narrative.scenes_of("world-town-ch01")}
    assert set(rows) == {1, 2, 3}
    assert rows[1].status is SceneStatus.PLANNED
    assert rows[2].status is SceneStatus.PLANNED
    assert rows[3].status is SceneStatus.DISCARDED

    # The r1 row's bytes never moved (append-only, and no rewrite of
    # the burned ids).
    r1 = narrative.get_plan("world-town-ch01-bp-r1")
    assert r1 is not None
    assert r1.scenes == read_back
    assert encode_scenes(r1.scenes) == encode_scenes(read_back)


def test_a_burned_identity_disagreeing_with_its_ref_is_refused(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    narrative: SqliteNarrativeStore,
    director: Director,
) -> None:
    """The identity pair's agreement, both halves: payload-local (the
    tail index disagrees — refused without touching the database) and
    anchored (the tail agrees but the full string names a different
    chapter's identity — refused at the resolution)."""

    _seed_town(conn, world_store, cast_store)
    opened = director.open_next_chapter(TOWN, _blueprint(), NOW)
    assert isinstance(opened, Ok)

    bad_pair = _scene("actor-lia", ("actor-lia", "pc-you")) | {
        "scene_ref": 1,
        "scene_id": "world-town-ch01-s02",
    }
    payload_local = director.revise_blueprint(
        "world-town-ch01", _blueprint(scenes=[bad_pair]), LATER
    )
    assert isinstance(payload_local, Err)
    assert payload_local.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "must agree" in payload_local.error.message

    foreign_id = _scene("actor-lia", ("actor-lia", "pc-you")) | {
        "scene_ref": 1,
        "scene_id": "world-elsewhere-ch01-s01",
    }
    anchored = director.revise_blueprint(
        "world-town-ch01", _blueprint(scenes=[foreign_id]), LATER
    )
    assert isinstance(anchored, Err)
    assert anchored.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "disagrees" in anchored.error.message

    # Neither refusal minted a revision.
    assert len(narrative.plans_of("world-town-ch01")) == 1


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
    lands), and an empty scene list is **refused** — the V3-4R
    non-emptiness law, overturning the V3-4 pin that called it legal —
    again with no new revision minted and every anchor left standing."""

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
    assert isinstance(empty_scenes, Err)
    assert empty_scenes.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "scenes" in empty_scenes.error.message
    assert len(narrative.plans_of("world-town-ch01")) == 1
    assert [
        row.status for row in narrative.scenes_of("world-town-ch01")
    ] == [SceneStatus.PLANNED]


def test_revise_blueprint_refuses_a_settled_chapter(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    narrative: SqliteNarrativeStore,
    director: Director,
) -> None:
    """The review's F3 guard: a ``SETTLING`` or ``CLOSED`` chapter has no
    「剩余部分」 left to replan (§21 「CLOSED 不可 reopen；修正走后续
    章」 / §24 「只重规划剩余部分」) — revising one is refused
    ``VALIDATION_FAILED`` naming the status, **before anything is
    written** (no new plan revision, no new anchor, the chapter row
    untouched)."""

    _seed_town(conn, world_store, cast_store)
    opened = director.open_next_chapter(TOWN, _blueprint(), NOW)
    assert isinstance(opened, Ok)
    activated = narrative.activate_chapter(
        "world-town-ch01", 0, NOW, expected_state_version=1
    )
    assert isinstance(activated, Ok)
    settled = narrative.settle_chapter(
        "world-town-ch01", now=LATER, expected_state_version=2
    )
    assert isinstance(settled, Ok)

    refused_settling = director.revise_blueprint(
        "world-town-ch01", _blueprint(), LATER
    )
    assert isinstance(refused_settling, Err)
    assert refused_settling.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "SETTLING" in refused_settling.error.message
    assert len(narrative.plans_of("world-town-ch01")) == 1

    closed = narrative.close_chapter(
        "world-town-ch01", closed_at_tick=90, now=LATER, expected_state_version=3
    )
    assert isinstance(closed, Ok)
    refused_closed = director.revise_blueprint(
        "world-town-ch01", _blueprint(), LATER
    )
    assert isinstance(refused_closed, Err)
    assert refused_closed.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "CLOSED" in refused_closed.error.message
    # Nothing was written: one plan revision, one PLANNED anchor, the
    # chapter row's own version unmoved by the refused revisions.
    assert len(narrative.plans_of("world-town-ch01")) == 1
    chapter = narrative.get_chapter("world-town-ch01")
    assert chapter is not None
    assert chapter.status is ChapterStatus.CLOSED
    assert chapter.state_version == 4
    rows = narrative.scenes_of("world-town-ch01")
    assert [row.scene_index for row in rows] == [1]
    assert rows[0].status is SceneStatus.PLANNED


def test_a_world_without_a_bible_is_refused_before_anything_is_written(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    narrative: SqliteNarrativeStore,
    director: Director,
) -> None:
    """The fail-closed law (the V3-4R review's item 2; DATA §26.2.1's
    block): a world holding no ``CURRENT`` Bible revision plans nothing
    — ``open_next_chapter`` refuses ``NOT_FOUND`` naming the Bible
    (after the world-existence arm, before any write), and
    ``revise_blueprint`` refuses the same way for a chapter of that
    world — no chapter row, no plan revision, no anchor."""

    _seed_town(conn, world_store, cast_store, with_bible=False)
    refused = director.open_next_chapter(TOWN, _blueprint(), NOW)
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.NOT_FOUND
    assert "Bible" in refused.error.message
    assert narrative.chapters_of(TOWN) == ()

    created = narrative.create_chapter("world-town-ch01", TOWN, 1, NOW)
    assert isinstance(created, Ok)
    refused_revise = director.revise_blueprint(
        "world-town-ch01", _blueprint(), LATER
    )
    assert isinstance(refused_revise, Err)
    assert refused_revise.error.code is DomainErrorCode.NOT_FOUND
    assert "Bible" in refused_revise.error.message
    assert narrative.plans_of("world-town-ch01") == ()
    assert narrative.scenes_of("world-town-ch01") == ()


# ---------------------------------------------------------------------------
# 5. Plan≠Canon (the cut's pin) and the V2 chain
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
# 6. the chain head (V3-4 itself added no migration)
# ---------------------------------------------------------------------------


def test_the_chain_head_moved_on_after_this_cut() -> None:
    """The cut's own historical pin: V3-4 shipped **zero migration** —
    the shared constants and the applied chain ended at 0032 while it
    was the head — and V3-5's ``0033_segment_commit`` then V3-5R's
    ``0034_segment_terminality`` moved them
    afterwards (TASK-OPI-be7b094f…34 / TASK-OPI-dc1bafdf…13). The live
    lineage the shared
    constants carry is pinned here; V3-4's own claim is the sentence
    above, kept as history."""

    assert MIGRATION_IDS[-1] == "0034_segment_terminality"
    assert SCHEMA_HEAD_FILE == "0034_segment_terminality.sql"
    assert SCHEMA_HEAD_VERSION == "34"
    assert "0032_actor_profile_world_fk" in MIGRATION_IDS
