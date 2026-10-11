"""V3-2 — the World Bible (seven pin groups).

The Narrative V3 program's second cut (TASK-OPI-bab4da9f…29 /
VAL-OPI-bab4da9f…33): migration 0030's ``world_bible_revision`` table
plus one partial UNIQUE index, the store (:mod:`elc.world.bible`), and
the seed wired into the world's birth (``ensure_builtin_worlds`` /
``open_host``). The authority contract was already canonical — DATA
§26.2.1's entity contract, DOMAIN §20.3-6 and N-INV-006, the design
supplement's authority direction (World Bible → projection → legacy
view, never the reverse), IMPLEMENTATION_PLAN §20's V3-2 row. The
groups:

1. **migration and shape** — the column set verbatim (PRAGMA order),
   the status CHECK's two-word vocabulary (a third word refuses), the
   ``revision > 0`` and ``parent_revision < revision`` CHECKs, the
   ``UNIQUE (world_id, revision)`` idempotency key, the **partial
   UNIQUE** admitting at most one ``CURRENT`` row per world (two
   CURRENT rows refuse; a CURRENT beside a SUPERSEDED row is legal), a
   dangling ``world_id`` refused by the table's own FK, and the chain
   self-pin (the shared constants say ``0030_world_bible`` / ``30``,
   a fresh database stamps exactly that);
2. **open-time seed** — a builtin package's birth carries its Bible:
   revision 1, ``CURRENT``, ``parent_revision`` None, the premise
   being the package's setting prose joined with `` · ``, the other
   thirteen fields honestly empty, the derived id
   ``bible-<token>-0001``; a replayed seed writes nothing;
3. **the N-INV-006 machine pin (this cut's core)** — the package file
   edited after the seed, then the seed re-run: the open succeeds, and
   the stored row is byte-identical to the first write (premise,
   ``created_at``, every field), one row still — a template's later
   update does not silently rewrite an existing world;
4. **versioning and CAS** — a revision lands revision 2 / CURRENT /
   parent 1, supersedes the old row in the same transaction (its
   ``updated_at`` and ``state_version`` move), rows are never deleted
   (count only grows), the history reads ascending; a stale
   ``expected_state_version`` is a ``CONFLICT`` with the database
   unchanged, a world with no current revision a ``NOT_FOUND``, and an
   empty field in a revision is honest undeclared — never inherited
   from the previous revision;
5. **the read/citation face** — an unseeded world answers ``None``
   (honest), a superseded revision stays citable by number exactly as
   it was written, and the history orders ascending;
6. **anti-double-authority / legacy zero-touch** — a seeded world
   leaves ``world_lore_fact`` at zero rows and ``world_bible_revision``
   at one; the store's source names no legacy lore table at all
   (source-level pin), and the two modules import cold (the P4-3
   cold-start discipline);
7. **the wiring face** — ``bible_store`` is a required keyword-only
   parameter (no caller can silently skip the seed), and the real
   composition root seeds the real builtin world's Bible (one row,
   revision 1, ``CURRENT``; a reopen writes nothing).
"""

from __future__ import annotations

import inspect
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from elc.host import open_host
from elc.persona.provider import ScriptedPersonaProvider
from elc.platform.db.epoch import open_runtime_epoch
from elc.platform.db.migrations import apply_migrations, schema_version
from elc.platform.types import DomainErrorCode, Err, Ok
from elc.world.bible import (
    BIBLE_FIELDS,
    BibleRevisionStatus,
    SqliteBibleStore,
)
from elc.world.package import (
    BUILTIN_WORLDS_DIR,
    WORLD_PACKAGE_VERSION,
    ensure_builtin_worlds,
    load_world_package,
)
from elc.world.store import SqliteWorldStore
from tests.conftest import (
    MIGRATION_IDS,
    SCHEMA_HEAD_FILE,
    SCHEMA_HEAD_VERSION,
    SRC_ROOT,
)

REPO = Path(__file__).resolve().parents[2]

NOW = "2026-10-12T00:00:00+00:00"
LATER = "2026-10-12T01:00:00+00:00"

TEST_WORLD_ID = "world-bibletest"

# The empty string every undeclared content field reads back as — the
# seed face's honest "the template never spoke this" (and the revise
# face's honest "the caller declared nothing here"), never an
# inheritance.
UNDECLARED = ""


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
def bible(conn: sqlite3.Connection) -> SqliteBibleStore:
    """The Bible store over the fresh database."""

    return SqliteBibleStore(conn, open_runtime_epoch(conn))


@pytest.fixture()
def world_store(conn: sqlite3.Connection) -> SqliteWorldStore:
    """The world store over the same fresh database."""

    return SqliteWorldStore(conn, open_runtime_epoch(conn))


def _write_world_dir(tmp_path: Path, setting: list[str]) -> Path:
    """One temporary worlds directory carrying one minimal valid
    package (the loader's required face: identity, calendar start,
    setting, cast, a one-event pool, a supply declaration). The cast
    persona's card is a caller concern — the seed tests wire
    ``persona_exists`` directly, so no card table is built here."""

    directory = tmp_path / "worlds"
    directory.mkdir(exist_ok=True)
    payload = {
        "world_id": TEST_WORLD_ID,
        "name": "Bibletest",
        "version": WORLD_PACKAGE_VERSION,
        "calendar_start": "2026-01-01",
        "setting": setting,
        "cast": [{"persona_id": "persona-nell-alder", "name": "Nell"}],
        "event_pool": [
            {
                "kind": "morning",
                "narration": "The mill wheel turns.",
                "narration_zh": "磨坊的水轮转了起来。",
                "days": 1,
            }
        ],
        "supply": {"families": ["DISC"], "note": "declared-not-consumed"},
    }
    (directory / f"{TEST_WORLD_ID}.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    return directory


def _seed_setting() -> list[str]:
    """The first seed's setting paragraphs — two of them, so the
    premise mapping (``" · ".join``) is pinned on a multi-paragraph
    package."""

    return [
        "A mill town wedged between two hills.",
        "The river drives everything here.",
    ]


def _revised_premise() -> str:
    """The explicit revision's premise — a different world-wording, the
    caller's own full-content decision."""

    return "A mill town the river owns outright."


def _bible_id(revision: int) -> str:
    """The derived revision id the package seed uses — the same law as
    ``elc.world.package._bible_id_for`` (the tests re-derive it so the
    pins check the stored ids against the derivation's output)."""

    return f"bible-bibletest-{revision:04d}"


def _row_count(conn: sqlite3.Connection, world_id: str) -> int:
    """The table's row count for one world (the raw read the zero-write
    pins count)."""

    return int(
        conn.execute(
            "SELECT COUNT(*) FROM world_bible_revision WHERE world_id = ?",
            (world_id,),
        ).fetchone()[0]
    )


def _seed_one_world(
    world_store: SqliteWorldStore,
    bible: SqliteBibleStore,
    tmp_path: Path,
) -> Path:
    """One temporary worlds directory, seeded through the real
    ``ensure_builtin_worlds`` pass — the helper every seed-side pin
    rides."""

    directory = _write_world_dir(tmp_path, _seed_setting())
    ensure_builtin_worlds(
        world_store,
        directory,
        persona_exists=lambda _: True,
        bible_store=bible,
    )
    return directory


# ---------------------------------------------------------------------------
# 1. migration and shape
# ---------------------------------------------------------------------------


def test_the_shared_constants_and_a_fresh_db_say_30() -> None:
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


def test_world_bible_revision_carries_the_contract_columns(
    conn: sqlite3.Connection,
) -> None:
    """The physical column set, in order — DATA §26.2.1's entity
    contract verbatim (the id, the world FK, the version pair, the
    status, the fourteen content fields in the canonical order, the
    bookkeeping pair, the CAS counter)."""

    columns = [
        str(row[1])
        for row in conn.execute(
            "PRAGMA table_info(world_bible_revision)"
        ).fetchall()
    ]
    assert columns == [
        "bible_revision_id",
        "world_id",
        "revision",
        "parent_revision",
        "status",
        *BIBLE_FIELDS,
        "created_at",
        "updated_at",
        "state_version",
    ]


def test_the_status_vocabulary_is_exactly_the_canonical_two_words(
    conn: sqlite3.Connection,
) -> None:
    """The CHECK's word list is ``CURRENT`` / ``SUPERSEDED`` — a third
    word (a lifecycle borrowed from another table) refuses at the
    storage level."""

    conn.execute(
        "INSERT INTO world (world_id, name, template_world_id, created_at)"
        " VALUES ('w', 'W', NULL, ?)",
        (NOW,),
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO world_bible_revision ("
            " bible_revision_id, world_id, revision, parent_revision,"
            " status, premise, genre, tone, calendar, physics,"
            " magic_rules, geography, society, politics, technology,"
            " religion, history, hard_rules, narrative_preferences,"
            " created_at, updated_at, state_version"
            ") VALUES ('b1', 'w', 1, NULL, 'ADOPTED',"
            " '', '', '', '', '', '', '', '', '', '', '', '', '', '',"
            " ?, ?, 1)",
            (NOW, NOW),
        )
    conn.rollback()


def test_the_revision_checks_and_the_unique_key_hold(
    conn: sqlite3.Connection,
) -> None:
    """``revision > 0`` and ``parent_revision < revision`` refuse
    upside-down history, and ``(world_id, revision)`` is the
    idempotency key — the same number twice under one world refuses."""

    conn.execute(
        "INSERT INTO world (world_id, name, template_world_id, created_at)"
        " VALUES ('w', 'W', NULL, ?)",
        (NOW,),
    )
    insert = (
        "INSERT INTO world_bible_revision ("
        " bible_revision_id, world_id, revision, parent_revision,"
        " status, premise, genre, tone, calendar, physics,"
        " magic_rules, geography, society, politics, technology,"
        " religion, history, hard_rules, narrative_preferences,"
        " created_at, updated_at, state_version"
        ") VALUES (?, 'w', ?, ?, 'CURRENT',"
        " '', '', '', '', '', '', '', '', '', '', '', '', '', '',"
        " ?, ?, 1)"
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(insert, ("b-zero", 0, None, NOW, NOW))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(insert, ("b-parent", 2, 2, NOW, NOW))
    conn.execute(insert, ("b-first", 1, None, NOW, NOW))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(insert, ("b-again", 1, None, NOW, NOW))
    conn.rollback()


def test_one_current_per_world_is_a_storage_fact(
    conn: sqlite3.Connection,
) -> None:
    """The partial UNIQUE index (the single-authority shape the 0029
    store's registered obligation names): two ``CURRENT`` rows under
    one world refuse, while a ``CURRENT`` row beside a ``SUPERSEDED``
    one is exactly what the append-only versioning keeps."""

    conn.execute(
        "INSERT INTO world (world_id, name, template_world_id, created_at)"
        " VALUES ('w', 'W', NULL, ?)",
        (NOW,),
    )
    insert = (
        "INSERT INTO world_bible_revision ("
        " bible_revision_id, world_id, revision, parent_revision,"
        " status, premise, genre, tone, calendar, physics,"
        " magic_rules, geography, society, politics, technology,"
        " religion, history, hard_rules, narrative_preferences,"
        " created_at, updated_at, state_version"
        ") VALUES (?, 'w', ?, ?, ?,"
        " '', '', '', '', '', '', '', '', '', '', '', '', '', '',"
        " ?, ?, 1)"
    )
    conn.execute(insert, ("b-1", 1, None, "CURRENT", NOW, NOW))
    conn.execute(insert, ("b-2", 2, 1, "SUPERSEDED", NOW, NOW))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(insert, ("b-3", 3, 2, "CURRENT", NOW, NOW))
    conn.rollback()


def test_a_dangling_world_id_is_refused_by_the_table_fk(
    conn: sqlite3.Connection,
) -> None:
    """The FK chain (``world_id`` → ``world``) is the table's own: a
    Bible revision for a world that does not exist refuses at the
    storage level (the store surfaces it as ``NOT_FOUND``)."""

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO world_bible_revision ("
            " bible_revision_id, world_id, revision, parent_revision,"
            " status, premise, genre, tone, calendar, physics,"
            " magic_rules, geography, society, politics, technology,"
            " religion, history, hard_rules, narrative_preferences,"
            " created_at, updated_at, state_version"
            ") VALUES ('b-ghost', 'world-nowhere', 1, NULL, 'CURRENT',"
            " '', '', '', '', '', '', '', '', '', '', '', '', '', '',"
            " ?, ?, 1)",
            (NOW, NOW),
        )
    conn.rollback()


# ---------------------------------------------------------------------------
# 2. open-time seed
# ---------------------------------------------------------------------------


def test_the_seed_lands_revision_one_with_the_package_premise(
    world_store: SqliteWorldStore,
    bible: SqliteBibleStore,
    tmp_path: Path,
) -> None:
    """The world's birth carries its Bible: revision 1, ``CURRENT``,
    no parent (the template's own word), the premise being the
    package's setting prose joined with `` · ``, the other thirteen
    content fields honestly empty, the derived id, both stamps the
    seed's ``now`` and ``state_version`` 1."""

    _seed_one_world(world_store, bible, tmp_path)
    current = bible.current_bible(TEST_WORLD_ID)
    assert current is not None
    assert current.bible_revision_id == _bible_id(1)
    assert current.world_id == TEST_WORLD_ID
    assert current.revision == 1
    assert current.parent_revision is None
    assert current.status is BibleRevisionStatus.CURRENT
    assert current.premise == " · ".join(_seed_setting())
    for field in BIBLE_FIELDS:
        if field == "premise":
            continue
        assert getattr(current, field) == UNDECLARED, field
    # The no-hidden-clock law on the seed path: the caller here is the
    # package seed, and its one ``now`` stamps both bookkeeping fields.
    assert current.created_at == current.updated_at
    assert current.state_version == 1


def test_the_world_row_and_the_bible_id_derive_together(
    world_store: SqliteWorldStore,
    bible: SqliteBibleStore,
    tmp_path: Path,
) -> None:
    """The seed lands through the world store's own create face — the
    world row exists, and the Bible hangs off it (the FK chain is the
    real one, not a parallel bookkeeping)."""

    _seed_one_world(world_store, bible, tmp_path)
    world = world_store.get_world(TEST_WORLD_ID)
    assert world is not None
    assert world.name == "Bibletest"
    revisions = bible.bible_revisions(TEST_WORLD_ID)
    assert [row.revision for row in revisions] == [1]


def test_a_replayed_seed_writes_nothing(
    world_store: SqliteWorldStore,
    bible: SqliteBibleStore,
    conn: sqlite3.Connection,
    tmp_path: Path,
) -> None:
    """An open re-seed is a no-op: the row count stays 1 and the stored
    row is field-for-field identical (its ``created_at`` included)."""

    _seed_one_world(world_store, bible, tmp_path)
    before = bible.current_bible(TEST_WORLD_ID)
    assert before is not None

    ensure_builtin_worlds(
        world_store,
        _write_world_dir(tmp_path, _seed_setting()),
        persona_exists=lambda _: True,
        bible_store=bible,
    )
    assert _row_count(conn, TEST_WORLD_ID) == 1
    after = bible.current_bible(TEST_WORLD_ID)
    assert after == before


# ---------------------------------------------------------------------------
# 3. the N-INV-006 machine pin (this cut's core)
# ---------------------------------------------------------------------------


def test_a_template_update_does_not_rewrite_the_seeded_world(
    world_store: SqliteWorldStore,
    bible: SqliteBibleStore,
    conn: sqlite3.Connection,
    tmp_path: Path,
) -> None:
    """The invariant's machine half: the package file edited between
    opens, then the seed re-run — the open succeeds, and the stored row
    is byte-identical to the first write (premise, ``created_at``,
    every content field), one row still. A template does not own an
    existing world's rewrite (DOMAIN §20.3-6 / N-INV-006); making a
    change so is an explicit revision decision, never a silent push."""

    directory = _seed_one_world(world_store, bible, tmp_path)
    before = bible.current_bible(TEST_WORLD_ID)
    assert before is not None

    edited_setting = [
        "A mill town the river owns outright.",
        "The millers answer to the flood season.",
    ]
    _write_world_dir(tmp_path, edited_setting)
    ensure_builtin_worlds(
        world_store,
        directory,
        persona_exists=lambda _: True,
        bible_store=bible,
    )

    assert _row_count(conn, TEST_WORLD_ID) == 1
    after = bible.current_bible(TEST_WORLD_ID)
    assert after == before
    assert after.premise == " · ".join(_seed_setting())
    assert after.created_at == before.created_at


# ---------------------------------------------------------------------------
# 4. versioning and CAS
# ---------------------------------------------------------------------------


def _revise_kwargs(**overrides: str) -> dict[str, str]:
    """The fourteen content fields as one explicit payload — the
    revision face's full-content contract (nothing rides on the
    previous revision)."""

    fields = dict.fromkeys(BIBLE_FIELDS, "")
    fields["premise"] = _revised_premise()
    fields["genre"] = "fable"
    fields["hard_rules"] = "No one lies about the river."
    fields.update(overrides)
    return fields


def test_a_revision_supersedes_and_appends(
    world_store: SqliteWorldStore,
    bible: SqliteBibleStore,
    conn: sqlite3.Connection,
    tmp_path: Path,
) -> None:
    """The versioning law: the new row is revision 2 / ``CURRENT`` /
    parent 1; the old row is ``SUPERSEDED`` in the same transaction
    (its ``updated_at`` moves, its ``state_version`` bumps); rows are
    never deleted (the count only grows) and the history reads
    ascending."""

    _seed_one_world(world_store, bible, tmp_path)
    before = bible.current_bible(TEST_WORLD_ID)
    assert before is not None

    moved = bible.revise_bible(
        _bible_id(2),
        TEST_WORLD_ID,
        expected_state_version=1,
        now=LATER,
        **_revise_kwargs(),
    )
    assert isinstance(moved, Ok)
    revised = moved.value
    assert revised.bible_revision_id == _bible_id(2)
    assert revised.revision == 2
    assert revised.parent_revision == 1
    assert revised.status is BibleRevisionStatus.CURRENT
    assert revised.premise == _revised_premise()
    assert revised.created_at == revised.updated_at == LATER
    assert revised.state_version == 1

    rows = bible.bible_revisions(TEST_WORLD_ID)
    assert [row.revision for row in rows] == [1, 2]
    superseded = rows[0]
    assert superseded.status is BibleRevisionStatus.SUPERSEDED
    assert superseded.updated_at == LATER
    assert superseded.state_version == 2
    # The supersede moves the word, the bookkeeping stamp and the
    # counter — the row's own writing (its created_at) is untouched.
    assert superseded.created_at == before.created_at
    assert _row_count(conn, TEST_WORLD_ID) == 2


def test_a_stale_expected_version_is_a_conflict_and_writes_nothing(
    world_store: SqliteWorldStore,
    bible: SqliteBibleStore,
    conn: sqlite3.Connection,
    tmp_path: Path,
) -> None:
    """The CAS law: a stale ``expected_state_version`` is refused
    ``CONFLICT`` (the expected and actual counters ride the message)
    and the database is exactly as it was."""

    _seed_one_world(world_store, bible, tmp_path)

    refused = bible.revise_bible(
        _bible_id(2),
        TEST_WORLD_ID,
        expected_state_version=99,
        now=LATER,
        **_revise_kwargs(),
    )
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.CONFLICT
    assert "99" in refused.error.message
    assert _row_count(conn, TEST_WORLD_ID) == 1
    current = bible.current_bible(TEST_WORLD_ID)
    assert current is not None
    assert current.revision == 1
    assert current.state_version == 1


def test_a_world_with_no_current_revision_cannot_revise(
    bible: SqliteBibleStore,
) -> None:
    """A world with no Bible revision (never seeded — here: never even
    created) has nothing to revise: ``NOT_FOUND``, in a human
    sentence."""

    refused = bible.revise_bible(
        _bible_id(1),
        "world-nowhere",
        expected_state_version=1,
        now=NOW,
        **_revise_kwargs(),
    )
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.NOT_FOUND
    assert "world-nowhere" in refused.error.message


def test_an_empty_field_is_undeclared_not_inherited(
    world_store: SqliteWorldStore,
    bible: SqliteBibleStore,
    tmp_path: Path,
) -> None:
    """The full-content law: a revision carries what its caller said
    and nothing else — an empty field in the new revision reads the
    empty string, never the previous revision's word (the caller says
    what the world is like; the store does not carry old words
    forward)."""

    _seed_one_world(world_store, bible, tmp_path)
    first = bible.revise_bible(
        _bible_id(2),
        TEST_WORLD_ID,
        expected_state_version=1,
        now=LATER,
        **_revise_kwargs(),
    )
    assert isinstance(first, Ok)
    assert first.value.genre == "fable"

    second = bible.revise_bible(
        _bible_id(3),
        TEST_WORLD_ID,
        expected_state_version=1,
        now=LATER,
        **_revise_kwargs(genre=""),
    )
    assert isinstance(second, Ok)
    assert second.value.revision == 3
    assert second.value.genre == UNDECLARED

    history = bible.bible_revisions(TEST_WORLD_ID)
    assert history[1].genre == "fable"  # the previous revision, intact
    assert history[2].genre == UNDECLARED  # not inherited


# ---------------------------------------------------------------------------
# 5. the read/citation face
# ---------------------------------------------------------------------------


def test_an_unseeded_world_answers_none(bible: SqliteBibleStore) -> None:
    """The honest zero: a world whose Bible was never seeded has no
    current revision and no history — answers, not errors."""

    assert bible.current_bible("world-nowhere") is None
    assert bible.get_bible("world-nowhere", 1) is None
    assert bible.bible_revisions("world-nowhere") == ()


def test_a_superseded_revision_stays_citable(
    world_store: SqliteWorldStore,
    bible: SqliteBibleStore,
    tmp_path: Path,
) -> None:
    """The citation read: after a revision, revision 1 answers by
    number exactly as it was written — the fourteen content fields,
    the identity and the original creation stamp are the pre-revision
    row's own (the supersede moved only the word, the bookkeeping
    stamp and the counter)."""

    _seed_one_world(world_store, bible, tmp_path)
    before = bible.current_bible(TEST_WORLD_ID)
    assert before is not None

    moved = bible.revise_bible(
        _bible_id(2),
        TEST_WORLD_ID,
        expected_state_version=1,
        now=LATER,
        **_revise_kwargs(),
    )
    assert isinstance(moved, Ok)

    cited = bible.get_bible(TEST_WORLD_ID, 1)
    assert cited is not None
    assert cited.status is BibleRevisionStatus.SUPERSEDED
    # The citation is the revision's own writing: the fourteen content
    # fields, the identity and the original creation stamp answer
    # exactly as they were written (only the supersede's bookkeeping —
    # status / updated_at / state_version — has moved, the versioning
    # law group 4 pins).
    for field in BIBLE_FIELDS:
        assert getattr(cited, field) == getattr(before, field), field
    assert cited.bible_revision_id == before.bible_revision_id
    assert cited.revision == before.revision
    assert cited.parent_revision == before.parent_revision
    assert cited.created_at == before.created_at
    assert cited.premise == " · ".join(_seed_setting())


# ---------------------------------------------------------------------------
# 6. anti-double-authority / legacy zero-touch
# ---------------------------------------------------------------------------


def test_a_seeded_world_writes_no_legacy_lore(
    world_store: SqliteWorldStore,
    bible: SqliteBibleStore,
    conn: sqlite3.Connection,
    tmp_path: Path,
) -> None:
    """One authority: the seed touches the Bible table and the legacy
    lore table not at all — zero rows there, one row here."""

    _seed_one_world(world_store, bible, tmp_path)
    assert (
        conn.execute("SELECT COUNT(*) FROM world_lore_fact").fetchone()[0]
        == 0
    )
    assert conn.execute(
        "SELECT COUNT(*) FROM world_bible_revision"
    ).fetchone()[0] == 1


def test_the_bible_store_names_no_legacy_table() -> None:
    """The source-level zero-reference pin: the store's every SQL
    statement names ``world_bible_revision`` (and, through the FK, the
    ``world`` table) — the legacy lore vocabulary appears nowhere in
    the module, so a reverse projection cannot hide here."""

    text = (SRC_ROOT / "world" / "bible.py").read_text(encoding="utf-8")
    assert "world_lore" not in text


def test_the_bible_modules_import_from_a_cold_interpreter() -> None:
    """The cold-start pin (the P4-3 discipline): a fresh interpreter
    importing the two modules first must succeed — no import cycle may
    hide behind a lucky test-session order."""

    env = dict(
        os.environ,
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=str(REPO / "src"),
    )
    proc = subprocess.run(
        [sys.executable, "-c", "import elc.world.bible, elc.world.package"],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr


# ---------------------------------------------------------------------------
# 7. the wiring face
# ---------------------------------------------------------------------------


def test_bible_store_is_a_required_keyword_parameter() -> None:
    """The signature law: ``bible_store`` is keyword-only and has no
    default — no caller can silently skip the Bible seed (the
    ``persona_exists`` keyword's own posture)."""

    parameters = inspect.signature(ensure_builtin_worlds).parameters
    assert "bible_store" in parameters
    parameter = parameters["bible_store"]
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is inspect.Parameter.empty

    with pytest.raises(TypeError):
        ensure_builtin_worlds(None, None, persona_exists=lambda _: True)


def test_the_composition_root_seeds_the_builtin_worlds_bible(
    tmp_path: Path,
) -> None:
    """The real machine: an ``open_host`` pass seeds the real builtin
    world's Bible — exactly one row for ``world-berrymoor``, revision
    1, ``CURRENT``, its premise the shipped package's setting prose
    joined the seed's way; a reopen writes nothing (the seed's
    idempotence through the real wiring)."""

    package = load_world_package(BUILTIN_WORLDS_DIR / "berrymoor.json").value
    package_premise = " · ".join(package.setting)

    counts: list[int] = []
    for _ in range(2):
        host = open_host(
            tmp_path / "app.db", provider=ScriptedPersonaProvider()
        )
        try:
            counts.append(
                int(
                    host.db.execute(
                        "SELECT COUNT(*) FROM world_bible_revision"
                        " WHERE world_id = 'world-berrymoor'"
                    ).fetchone()[0]
                )
            )
        finally:
            host.close()
    assert counts[0] == counts[1] == 1

    host = open_host(tmp_path / "app.db", provider=ScriptedPersonaProvider())
    try:
        store = SqliteBibleStore(host.db, open_runtime_epoch(host.db))
        current = store.current_bible("world-berrymoor")
        assert current is not None
        assert current.revision == 1
        assert current.parent_revision is None
        assert current.status is BibleRevisionStatus.CURRENT
        assert current.premise == package_premise
    finally:
        host.close()
