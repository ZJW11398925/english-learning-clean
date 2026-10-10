"""C2 — the storyline layer (DEC-OPI-b290799a…45, the plot layer's own
cut).

The cognition-and-narrative-quality doc's 域二 (裁断点③④): the story's
arcs are a first-class structure — a world ships one to three opening
lines, the narrator's prompt carries the active ones, and a beat closes
one by proposing ``storyline:<line_id>`` = ``resolved`` through the
ordinary effects settlement. The two-layer law: the structure row and
the projection each retire a line from the active read, and neither
writes the other. Pin groups:

1. **migration pins** — 0028 is the registered head, the
   ``world_storyline`` table carries its seven columns and their
   posture (the world FK, the three-word CHECK, the ``'active'``
   DEFAULT, the RESTRICT posture), the stamps read ``'28'``, and the
   deletion face keeps the table (the world-owned half);
2. **the store face** — ``create_storyline`` is idempotent by id and
   refuses a shape clash and a dangling world; ``resolve_storyline`` is
   the row's one legal move (active → resolved, exactly once);
   ``list_storylines`` reads every lifecycle word in id order;
   ``active_storylines`` is the two-layer read (structure ``active``
   **and** no CURRENT resolved claim under the line's key);
3. **package v5** — the loader decodes the optional
   ``initial_storylines`` section strictly (``{theme, resolve_at}``
   pairs; absent / empty legal; malformed refused naming the entry),
   the shipped Berrymoor file carries its opening arcs, and the seed
   lands them through the idempotent create face (derived
   ``line-<token>-<ordinal>`` ids, ``active`` with no opening event);
4. **the narrator's material face** — the active-storylines section
   rides only when the caller reads (``None`` keeps the prompt byte for
   byte), carries each triple with its id, teaches the closure proposal
   with the canonical key, and an empty read earns the honest
   no-open-arcs line and no closure teaching; malformed triples are a
   ``ValueError``;
5. **the closure loop** — a beat's ``storyline:<line_id>`` =
   ``resolved`` proposal settles into ``world_state_fact``, the line
   retires from the next step's prompt through the store's active read
   alone (no run-row move, no second state machine, the structure row
   untouched), and with no lines the step's prompt still carries the
   honest empty section;
6. **the web bridge** — the served stack reads the bound world's
   storylines **per step** and the narrator's prompt carries the
   shipped Berrymoor arcs (the seed's derived ids and themes).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from elc.deletion.types import (
    GLOBAL_CONTENT_TABLES,
    RETAINED_TABLES,
    SWEPT_TABLES,
)
from elc.host import open_host
from elc.persona.provider import ScriptedPersonaProvider
from elc.persona.types import ProviderOutput
from elc.platform.db.epoch import open_runtime_epoch
from elc.platform.db.migrations import apply_migrations
from elc.platform.types import DomainErrorCode, Err, Ok
from elc.world.engine.orchestrate import run_generated_step
from elc.world.narrator import build_narrator_prompt
from elc.world.package import (
    BUILTIN_WORLDS_DIR,
    WORLD_PACKAGE_VERSION,
    ensure_builtin_worlds,
    load_world_package,
)
from elc.world.store import SqliteWorldStore, WorldStorylineRecord
from elc.world.types import (
    STORYLINE_EFFECT_KEY_PREFIX,
    STORYLINE_RESOLVED_STATEMENT,
    StateEffect,
    WorldEvent,
    storyline_effect_key,
)
from tests.conftest import (
    MIGRATION_IDS,
    REPO_ROOT,
    SCHEMA_HEAD_FILE,
    SCHEMA_HEAD_VERSION,
)
from tests.host.test_w1_web import web_stack
from tests.host.test_wr2_post_turn_wiring import (
    NARRATOR_MARK,
    BeatsProvider,
)
from tests.world.test_wr2_narrator import (
    _beat,
    _beats,
    _package,
    _ScriptedNarrator,
    _seed_world,
)

NOW = "2026-10-10T12:00:00+00:00"
WORLD = "world-main"
LINE = "line-1"
THEME = "The order book is thinning."
RESOLVE_AT = "Nell settles the bindery's future."
PACKAGE_PATH = BUILTIN_WORLDS_DIR / "berrymoor.json"

#: The section header, spelled as a literal here (the prompt's own
#: door name — a rename turns every pin below red).
STORYLINE_HEADER = "== Active storylines =="

#: The closure teaching's canonical shape (the exact literal the prompt
#: must carry — the format the store's active read filters on).
CLOSURE_SHAPE = '{"key": "storyline:<line_id>", "statement": "resolved"}'


# ---------------------------------------------------------------------------
# shared fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    """A fresh, fully migrated app.db connection with the production
    foreign-keys-ON profile (the wr2 fixture shape)."""

    db = sqlite3.connect(tmp_path / "app.db")
    db.execute("PRAGMA foreign_keys=ON")
    apply_migrations(db)
    return db


@pytest.fixture()
def store(conn: sqlite3.Connection) -> SqliteWorldStore:
    return SqliteWorldStore(conn, open_runtime_epoch(conn))


def _land_claim(store: SqliteWorldStore, line_id: str, statement: str) -> None:
    """Settle one ``storyline:<line_id>`` claim through the ordinary
    event pipe — the only writer of the projection (C1-b's settlement:
    the key's CURRENT fact flips SUPERSEDED, the claim lands CURRENT)."""

    landed = store.record_event(
        WorldEvent(
            event_id=f"e-{line_id}-{statement}",
            world_id=WORLD,
            kind="arc-beat",
            narration=f"the arc claimed {statement!r}",
            effects=(
                StateEffect(
                    key=storyline_effect_key(line_id), statement=statement
                ),
            ),
            occurred_at=NOW,
            source="world_narrator",
            participants=(),
            run_id=None,
        )
    )
    assert isinstance(landed, Ok), landed


# ---------------------------------------------------------------------------
# 1 — the migration (VAL ①)
# ---------------------------------------------------------------------------


def test_0028_is_the_registered_head() -> None:
    """C2's migration is the chain's newest entry, immediately behind
    C1-a's 0027; the shared constants say so, and the stamp a fresh
    database carries is 28."""

    assert MIGRATION_IDS[-1] == "0028_world_storyline"
    assert MIGRATION_IDS[-2] == "0027_chronicle_attribution"
    assert SCHEMA_HEAD_FILE == "0028_world_storyline.sql"
    assert SCHEMA_HEAD_VERSION == "28"
    assert (REPO_ROOT / "migrations" / SCHEMA_HEAD_FILE).is_file()

    fresh = sqlite3.connect(":memory:")
    fresh.execute("PRAGMA foreign_keys=ON")
    applied = apply_migrations(fresh)
    assert applied[-1] == "0028_world_storyline"
    assert applied[-2] == "0027_chronicle_attribution"


def test_world_storyline_carries_its_columns_and_posture() -> None:
    """The physical column set, in order (the id/type/pk triplets PRAGMA
    reports; SQLite's ``notnull`` flag reads 0 on the TEXT primary key —
    the 0023–0026 tables' own shape, the PK is the declaration), plus
    the schema's own refusals: the single world FK, the three-word
    lifecycle CHECK, the ``'active'`` DEFAULT (the create face's only
    starting word), the RESTRICT posture against deleting a world with
    lines, and the head's double stamp."""

    fresh = sqlite3.connect(":memory:")
    fresh.execute("PRAGMA foreign_keys=ON")
    apply_migrations(fresh)
    rows = fresh.execute("PRAGMA table_info(world_storyline)").fetchall()
    assert [(str(row[1]), str(row[2]), int(row[5])) for row in rows] == [
        ("line_id", "TEXT", 1),
        ("world_id", "TEXT", 0),
        ("theme", "TEXT", 0),
        ("opened_by", "TEXT", 0),
        ("status", "TEXT", 0),
        ("resolve_at", "TEXT", 0),
        ("created_at", "TEXT", 0),
    ]
    by_name = {
        str(row[1]): (int(row[3]), row[4]) for row in rows
    }
    assert by_name["line_id"] == (0, None)
    assert by_name["world_id"] == (1, None)
    assert by_name["theme"] == (1, None)
    assert by_name["opened_by"] == (0, None)
    assert by_name["status"] == (1, "'active'")
    assert by_name["resolve_at"] == (1, None)
    assert by_name["created_at"] == (1, None)

    foreign_keys = fresh.execute(
        "PRAGMA foreign_key_list(world_storyline)"
    ).fetchall()
    assert sorted(
        (str(row[2]), str(row[3]), str(row[4])) for row in foreign_keys
    ) == [("world", "world_id", "world_id")]

    fresh.execute(
        "INSERT INTO world (world_id, name, created_at) VALUES ('w', 'W', ?)",
        (NOW,),
    )
    base = (
        "INSERT INTO world_storyline (line_id, world_id, theme, opened_by,"
        " status, resolve_at, created_at)"
        " VALUES (?, 'w', 'theme', NULL, ?, ?, ?)"
    )
    fresh.execute(base, ("l-active", "active", RESOLVE_AT, NOW))
    fresh.execute(base, ("l-resolved", "resolved", RESOLVE_AT, NOW))
    # ``settled`` sits in the vocabulary for the later cut (spec §5.4's
    # 整线沉降) — this cut's faces never write it, the schema must name it.
    fresh.execute(base, ("l-settled", "settled", RESOLVE_AT, NOW))
    with pytest.raises(sqlite3.IntegrityError):
        fresh.execute(base, ("l-seen", "SEEN", RESOLVE_AT, NOW))

    # The DEFAULT is the create face's only starting word: a status-less
    # insert lands ``active``.
    fresh.execute(
        "INSERT INTO world_storyline (line_id, world_id, theme,"
        " resolve_at, created_at) VALUES ('l-default', 'w', 't', ?, ?)",
        (RESOLVE_AT, NOW),
    )
    assert fresh.execute(
        "SELECT status FROM world_storyline WHERE line_id = 'l-default'"
    ).fetchone() == ("active",)

    # RESTRICT posture: a world with lines does not delete.
    with pytest.raises(sqlite3.IntegrityError):
        fresh.execute("DELETE FROM world WHERE world_id = 'w'")

    stamps = dict(
        fresh.execute(
            "SELECT key, value FROM schema_meta"
            " WHERE key LIKE '%schema_version%'"
        ).fetchall()
    )
    assert stamps == {
        "schema_version": SCHEMA_HEAD_VERSION,
        "runtime_schema_version": SCHEMA_HEAD_VERSION,
    }


def test_the_deletion_face_classifies_the_storyline_table() -> None:
    """The §23 closure requires every table classified: 0028's table
    joins the world-owned keep half (registration, not deletion
    semantics — the conservative reading every world table has had),
    and belongs to no sweep."""

    assert "world_storyline" in GLOBAL_CONTENT_TABLES
    assert "world_storyline" not in SWEPT_TABLES
    assert "world_storyline" not in RETAINED_TABLES


# ---------------------------------------------------------------------------
# 2 — the store face (VAL ②)
# ---------------------------------------------------------------------------


def test_the_key_derivation_is_single_sourced() -> None:
    """The canonical key's own words: the prefix, the statement and the
    derivation read as literals here — the prompt teaches this format
    and the store's active read filters on it, one spelling both
    sides."""

    assert STORYLINE_EFFECT_KEY_PREFIX == "storyline:"
    assert STORYLINE_RESOLVED_STATEMENT == "resolved"
    assert storyline_effect_key("line-a") == "storyline:line-a"


def test_create_is_idempotent_by_id_and_refuses_the_rest(
    store: SqliteWorldStore,
) -> None:
    """The seed's entry: the same id and shape replays as the stored row
    unchanged (status included — the create face never rewrites a
    lifecycle word); a same-id different shape is ``CONFLICT``; a
    dangling world is ``NOT_FOUND`` (the FK's own refusal, wrapped)."""

    _seed_world(store)
    first = store.create_storyline(LINE, WORLD, THEME, None, RESOLVE_AT, NOW)
    assert isinstance(first, Ok), first
    assert first.value == WorldStorylineRecord(
        line_id=LINE,
        world_id=WORLD,
        theme=THEME,
        opened_by=None,
        status="active",
        resolve_at=RESOLVE_AT,
        created_at=NOW,
    )
    replay = store.create_storyline(
        LINE, WORLD, THEME, None, RESOLVE_AT, "2027-01-01T00:00:00+00:00"
    )
    assert isinstance(replay, Ok)
    assert replay.value == first.value, (
        "a same-shape replay answers the stored row, nothing rewritten"
    )
    conflicting = store.create_storyline(
        LINE, WORLD, "Another theme.", None, RESOLVE_AT, NOW
    )
    assert isinstance(conflicting, Err)
    assert conflicting.error.code is DomainErrorCode.CONFLICT
    dangling = store.create_storyline(
        "line-x", "world-absent", THEME, None, RESOLVE_AT, NOW
    )
    assert isinstance(dangling, Err)
    assert dangling.error.code is DomainErrorCode.NOT_FOUND
    assert store.list_storylines(WORLD) == (first.value,)


def test_resolve_moves_active_to_resolved_exactly_once(
    store: SqliteWorldStore,
) -> None:
    """The structure's one legal move: active → resolved; a second
    resolve is ``VALIDATION_FAILED`` (closing is not a no-op and does
    not close twice), an unknown line is ``NOT_FOUND``. The flip
    retires the line from the active read — the structure's own word."""

    _seed_world(store)
    assert isinstance(
        store.create_storyline(LINE, WORLD, THEME, None, RESOLVE_AT, NOW),
        Ok,
    )
    resolved = store.resolve_storyline(LINE, NOW)
    assert isinstance(resolved, Ok), resolved
    assert resolved.value.status == "resolved"
    again = store.resolve_storyline(LINE, NOW)
    assert isinstance(again, Err)
    assert again.error.code is DomainErrorCode.VALIDATION_FAILED
    missing = store.resolve_storyline("line-absent", NOW)
    assert isinstance(missing, Err)
    assert missing.error.code is DomainErrorCode.NOT_FOUND

    assert store.active_storylines(WORLD) == ()
    assert [row.status for row in store.list_storylines(WORLD)] == [
        "resolved"
    ]


def test_active_storylines_filters_through_the_projection(
    store: SqliteWorldStore,
) -> None:
    """The two-layer read's core: a line retires when the projection
    carries a CURRENT ``storyline:<line_id>`` = ``resolved`` claim,
    while the structure row stays ``active`` (neither face writes the
    other); a different statement under the key is a state claim about
    the line, never its retirement; the CURRENT word is the live word
    (the projection's own supersede law)."""

    _seed_world(store)
    for line_id in ("line-a", "line-b", "line-c"):
        assert isinstance(
            store.create_storyline(
                line_id, WORLD, THEME, None, RESOLVE_AT, NOW
            ),
            Ok,
        )
    assert [row.line_id for row in store.active_storylines(WORLD)] == [
        "line-a",
        "line-b",
        "line-c",
    ]

    # A different statement under the line's own key: a claim, not a
    # closure.
    _land_claim(store, "line-c", "advancing")
    assert [row.line_id for row in store.active_storylines(WORLD)] == [
        "line-a",
        "line-b",
        "line-c",
    ]

    # The canonical closure: the projection's word retires the line.
    _land_claim(store, "line-b", STORYLINE_RESOLVED_STATEMENT)
    assert [row.line_id for row in store.active_storylines(WORLD)] == [
        "line-a",
        "line-c",
    ]
    # The structure rows are untouched (zero status writes by the
    # projection side), and the list read still shows every word.
    assert {row.line_id: row.status for row in store.list_storylines(WORLD)} == {
        "line-a": "active",
        "line-b": "active",
        "line-c": "active",
    }

    # The CURRENT word is the live word: a later claim supersedes the
    # closure exactly as every projection claim supersedes its key.
    _land_claim(store, "line-b", "reopened")
    assert [row.line_id for row in store.active_storylines(WORLD)] == [
        "line-a",
        "line-b",
        "line-c",
    ]
    assert {
        fact.canonical_key: fact.statement
        for fact in store.current_facts(WORLD)
    }["storyline:line-b"] == "reopened"


def test_active_storylines_are_scoped_to_their_world(
    store: SqliteWorldStore,
) -> None:
    """Two worlds, two read faces: a line lands in one world's reads
    only — the world's own slice, the id-ascending durable order."""

    _seed_world(store)
    assert isinstance(store.create_world("world-other", "Other", None, NOW), Ok)
    assert isinstance(
        store.create_storyline("line-b", WORLD, THEME, None, RESOLVE_AT, NOW),
        Ok,
    )
    assert isinstance(
        store.create_storyline(
            "line-a", "world-other", THEME, None, RESOLVE_AT, NOW
        ),
        Ok,
    )
    assert [row.line_id for row in store.list_storylines(WORLD)] == ["line-b"]
    assert [row.line_id for row in store.active_storylines(WORLD)] == [
        "line-b"
    ]
    assert [row.line_id for row in store.active_storylines("world-other")] == [
        "line-a"
    ]


# ---------------------------------------------------------------------------
# 3 — package v5 and the seed (VAL ③)
# ---------------------------------------------------------------------------


def _payload() -> dict[str, object]:
    """One minimal valid v5 package payload — the negative tests mutate
    a copy of this and expect the loader to refuse the copy, never the
    shipped Berrymoor file."""

    return {
        "world_id": "world-x",
        "name": "X",
        "version": WORLD_PACKAGE_VERSION,
        "calendar_start": "2025-09-14",
        "setting": ["one", "two", "three"],
        "cast": [{"persona_id": "persona-nell", "name": "Nell"}],
        "event_pool": [
            {
                "kind": "k",
                "narration": "n",
                "narration_zh": "n-中文",
                "days": 1,
            }
        ],
        "supply": {"note": "declared-not-consumed", "families": ["DISC"]},
    }


def _write_package(tmp_path: Path, payload: object, name: str) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_v5_storylines_decode_and_absent_is_legal(tmp_path: Path) -> None:
    """The section decodes strictly into ``(theme, resolve_at)`` pairs;
    its absence and an explicit empty array are both legal — an honest
    no-opening-arcs world."""

    payload = _payload()
    payload["initial_storylines"] = [
        {"theme": "theme one", "resolve_at": "resolve one"},
        {"theme": "theme two", "resolve_at": "resolve two"},
    ]
    loaded = load_world_package(_write_package(tmp_path, payload, "a.json"))
    assert isinstance(loaded, Ok), loaded.error.message
    assert loaded.value.version == WORLD_PACKAGE_VERSION == 5
    assert loaded.value.initial_storylines == (
        ("theme one", "resolve one"),
        ("theme two", "resolve two"),
    )

    absent = load_world_package(
        _write_package(tmp_path, _payload(), "b.json")
    )
    assert isinstance(absent, Ok)
    assert absent.value.initial_storylines == ()

    empty_payload = _payload()
    empty_payload["initial_storylines"] = []
    empty = load_world_package(
        _write_package(tmp_path, empty_payload, "c.json")
    )
    assert isinstance(empty, Ok)
    assert empty.value.initial_storylines == ()


def test_malformed_storyline_sections_are_refused(tmp_path: Path) -> None:
    """The strict decode: every entry is exactly ``{theme, resolve_at}``
    with both non-empty strings — anything else is a refusal naming the
    section (or its entry), never half an arc."""

    bad_entries: list[object] = [
        "not-a-list",
        [1],
        [{"theme": "only a theme"}],
        [{"theme": "t", "resolve_at": "r", "extra": "x"}],
        [{"theme": "", "resolve_at": "r"}],
        [{"theme": "t", "resolve_at": "   "}],
        [{"theme": 7, "resolve_at": "r"}],
    ]
    for index, bad in enumerate(bad_entries):
        payload = _payload()
        payload["initial_storylines"] = bad
        result = load_world_package(
            _write_package(tmp_path, payload, f"bad-{index}.json")
        )
        assert isinstance(result, Err), (index, bad)
        assert "initial_storylines" in result.error.message, (index, bad)


def test_the_shipped_package_carries_its_opening_arcs() -> None:
    """Berrymoor ships one to three opening arcs (裁断点③'s v1 cap), each
    a real theme plus its closure condition — the seed's source."""

    loaded = load_world_package(PACKAGE_PATH)
    assert isinstance(loaded, Ok), loaded.error.message
    package = loaded.value
    assert package.version == WORLD_PACKAGE_VERSION == 5
    assert 1 <= len(package.initial_storylines) <= 3
    for theme, resolve_at in package.initial_storylines:
        assert isinstance(theme, str) and theme.strip()
        assert isinstance(resolve_at, str) and resolve_at.strip()


def test_berrymoor_seed_lands_the_storylines_idempotently(
    store: SqliteWorldStore,
) -> None:
    """The seed's landed shape: the derived id (``line-<world
    token>-<ordinal>``), the package's theme and resolve_at, ``active``
    with no opening event; a replayed seed re-derives the same ids and
    writes nothing (the stored rows, ``created_at`` included, are
    identical)."""

    package = load_world_package(PACKAGE_PATH).value
    ensure_builtin_worlds(
        store,
        BUILTIN_WORLDS_DIR,
        persona_exists=lambda persona_id: persona_id == "persona-nell-alder",
    )
    lines = store.list_storylines("world-berrymoor")
    assert [
        (
            row.line_id,
            row.theme,
            row.resolve_at,
            row.opened_by,
            row.status,
        )
        for row in lines
    ] == [
        (f"line-berrymoor-{index:04d}", theme, resolve_at, None, "active")
        for index, (theme, resolve_at) in enumerate(
            package.initial_storylines
        )
    ]
    assert store.active_storylines("world-berrymoor") == lines

    ensure_builtin_worlds(
        store,
        BUILTIN_WORLDS_DIR,
        persona_exists=lambda persona_id: persona_id == "persona-nell-alder",
    )
    assert store.list_storylines("world-berrymoor") == lines, (
        "a replayed seed writes nothing"
    )


def test_open_host_seeds_the_storylines_and_a_reopen_writes_nothing(
    tmp_path: Path,
) -> None:
    """The production path: the open's own seed lands Berrymoor's arcs,
    and a second open over the same app.db is a no-op (the same rows,
    their stamps included)."""

    counts: list[int] = []
    rows: list[list[tuple]] = []
    for _ in range(2):
        host = open_host(
            tmp_path / "app.db", provider=ScriptedPersonaProvider()
        )
        try:
            counts.append(
                int(
                    host.db.execute(
                        "SELECT COUNT(*) FROM world_storyline"
                    ).fetchone()[0]
                )
            )
            rows.append(
                host.db.execute(
                    "SELECT line_id, theme, status, created_at"
                    " FROM world_storyline ORDER BY line_id"
                ).fetchall()
            )
        finally:
            host.close()
    assert counts == [2, 2]
    assert rows[0] == rows[1] and rows[0], rows


# ---------------------------------------------------------------------------
# 4 — the narrator's material face (VAL ④)
# ---------------------------------------------------------------------------


def test_the_default_prompt_gains_nothing() -> None:
    """条件段定律：``active_storylines`` 缺席（显式 ``None`` 或不传）⇒
    无线区，且两种调用字节同一（两金针的法律，在本文件再证一次）。"""

    omitted = build_narrator_prompt(_package(), (), (), "zh")
    explicit = build_narrator_prompt(
        _package(), (), (), "zh", active_storylines=None
    )
    assert omitted == explicit
    assert STORYLINE_HEADER not in omitted
    assert "declare the line resolved" not in omitted


def test_the_storyline_section_rides_with_the_read() -> None:
    """线区钉：三件套逐字（line_id / theme / resolve_at），收束教学句
    带 canonical 提案形（``storyline:<line_id>`` = ``resolved``），位置在
    故事至今区之后、任务区之前，且只出现一次。"""

    lines = (("line-1", THEME, RESOLVE_AT),)
    prompt = build_narrator_prompt(
        _package(), (), ("A beat.",), "zh", active_storylines=lines
    )
    assert prompt.count(STORYLINE_HEADER) == 1
    assert f"- line-1: {THEME} (resolves when: {RESOLVE_AT})" in prompt
    assert CLOSURE_SHAPE in prompt
    assert prompt.index("== The story so far ==") < prompt.index(
        STORYLINE_HEADER
    )
    assert prompt.index(STORYLINE_HEADER) < prompt.index("== Your task ==")


def test_the_empty_read_gives_the_honest_line() -> None:
    """空读 ⇒ 诚实无线句且无收束教学（没有线可收——门只在有把手处教）；
    区仍在场（条件段的在场是调用方的，内容是 store 的）。"""

    prompt = build_narrator_prompt(
        _package(), (), (), "zh", active_storylines=()
    )
    assert STORYLINE_HEADER in prompt
    assert "(No storylines are open right now.)" in prompt
    assert "declare the line resolved" not in prompt


def test_the_section_refuses_malformed_entries() -> None:
    """形守卫：每条必须是三非空串的元组——错形 ``ValueError``（prompt
    面只透传，但透传的线必须成形）。"""

    bad_entries: list[object] = [
        [("line-1", "only two")],
        [["line-1", THEME, RESOLVE_AT]],
        [("line-1", "   ", RESOLVE_AT)],
        [("line-1", THEME, "")],
        [(7, THEME, RESOLVE_AT)],
    ]
    for bad in bad_entries:
        with pytest.raises(ValueError):
            build_narrator_prompt(
                _package(),
                (),
                (),
                "zh",
                active_storylines=bad,  # type: ignore[arg-type]
            )


# ---------------------------------------------------------------------------
# 5 — the step's seam and the closure loop (VAL ⑤)
# ---------------------------------------------------------------------------


def test_the_step_rides_the_read_through(store: SqliteWorldStore) -> None:
    """协议面缝合钉：``run_generated_step(active_storylines=...)`` 把读面
    送进叙事者 prompt（线区在场）；默认 ``None`` ⇒ 无线区（零变化默认）；
    空元组 ⇒ 诚实无线句。"""

    _seed_world(store)
    carrier = _ScriptedNarrator(ProviderOutput(text=_beats(_beat(days=1))))
    stepped = run_generated_step(
        store,
        WORLD,
        _package(),
        carrier,
        "turn-c2-seam-1",
        NOW,
        active_storylines=((LINE, THEME, RESOLVE_AT),),
    )
    assert isinstance(stepped, Ok), stepped
    assert STORYLINE_HEADER in carrier.prompts[0]
    assert LINE in carrier.prompts[0]

    bare = _ScriptedNarrator(ProviderOutput(text=_beats(_beat(days=1))))
    plain = run_generated_step(
        store, WORLD, _package(), bare, "turn-c2-seam-2", NOW
    )
    assert isinstance(plain, Ok)
    assert STORYLINE_HEADER not in bare.prompts[0]

    empty_read = _ScriptedNarrator(
        ProviderOutput(text=_beats(_beat(days=1)))
    )
    no_lines = run_generated_step(
        store,
        WORLD,
        _package(),
        empty_read,
        "turn-c2-seam-3",
        NOW,
        active_storylines=(),
    )
    assert isinstance(no_lines, Ok)
    assert STORYLINE_HEADER in empty_read.prompts[0]
    assert "(No storylines are open right now.)" in empty_read.prompts[0]


def test_a_beat_proposal_closes_the_line_at_the_projection(
    store: SqliteWorldStore,
) -> None:
    """收束闭环钉：beat 在 ``effects`` 里提案 canonical 收束 ⇒
    ``world_state_fact`` 落 CURRENT ``resolved`` ⇒ 该线自 store 的
    active 读退休 ⇒ 下一步的 prompt 不再含该线（且结构行保持 active——
    投影面与结构面互不代写）。"""

    _seed_world(store)
    assert isinstance(
        store.create_storyline(LINE, WORLD, THEME, None, RESOLVE_AT, NOW), Ok
    )
    closure = _beats(
        {
            "kind": "arc-closed",
            "narration": "The notice went up on the green door.",
            "days": 1,
            "effects": [
                {"key": storyline_effect_key(LINE), "statement": "resolved"}
            ],
        }
    )
    narrator = _ScriptedNarrator(ProviderOutput(text=closure))
    stepped = run_generated_step(
        store,
        WORLD,
        _package(),
        narrator,
        "turn-c2-close-1",
        NOW,
        active_storylines=tuple(
            (row.line_id, row.theme, row.resolve_at)
            for row in store.active_storylines(WORLD)
        ),
    )
    assert isinstance(stepped, Ok), stepped
    assert LINE in narrator.prompts[0] and THEME in narrator.prompts[0]

    facts = store.current_facts(WORLD)
    assert [
        (fact.canonical_key, fact.statement, fact.status) for fact in facts
    ] == [(storyline_effect_key(LINE), "resolved", "CURRENT")]
    assert store.active_storylines(WORLD) == ()
    (row,) = store.list_storylines(WORLD)
    assert row.status == "active", (
        "the projection retires the read; the structure row is written"
        " by resolve_storyline alone"
    )

    second = _ScriptedNarrator(ProviderOutput(text=_beats(_beat(days=1))))
    again = run_generated_step(
        store,
        WORLD,
        _package(),
        second,
        "turn-c2-close-2",
        NOW,
        active_storylines=tuple(
            (entry.line_id, entry.theme, entry.resolve_at)
            for entry in store.active_storylines(WORLD)
        ),
    )
    assert isinstance(again, Ok), again
    # The closure fact rides the current-state board (C1-b's own
    # section — the projection's live half), while the **storyline
    # section** lists nothing: the line retired from the active read.
    assert "- storyline:line-1: resolved" in second.prompts[0]
    section = second.prompts[0].split(STORYLINE_HEADER)[1].split("==")[0]
    assert "(No storylines are open right now.)" in section
    assert LINE not in section
    assert THEME not in section
    assert RESOLVE_AT not in section


# ---------------------------------------------------------------------------
# 6 — the web bridge (VAL ⑥)
# ---------------------------------------------------------------------------


def test_the_web_chain_feeds_the_storylines_into_the_prompt(
    tmp_path: Path,
) -> None:
    """web 桥钉：真栈起服务 ⇒ 开机 seed 落 Berrymoor 初始线 ⇒ 每步从
    store 真读 ⇒ 叙事者 prompt 含线区（派生的 line id、包的主题与收束
    条件逐字、canonical 收束提案形在场）。若有人把 active 读拆成恒空，
    本钉即 RED。"""

    app_db = tmp_path / "app.db"
    provider = BeatsProvider()
    with web_stack(app_db, provider=provider) as stack:
        status, _turn = stack.post(
            "/api/turn", {"text": "A letter from the coast."}
        )
        assert status == 200
    narrator_prompts = [
        prompt for prompt in provider.prompts if NARRATOR_MARK in prompt
    ]
    assert narrator_prompts, "the world chain dialed no narrator"
    prompt = narrator_prompts[0]
    package = load_world_package(PACKAGE_PATH).value
    first_theme, first_resolve_at = package.initial_storylines[0]
    assert STORYLINE_HEADER in prompt
    assert "line-berrymoor-0000" in prompt
    assert first_theme in prompt
    assert first_resolve_at in prompt
    assert CLOSURE_SHAPE in prompt
