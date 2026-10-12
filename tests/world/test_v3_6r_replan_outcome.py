"""V3-6R — the scope-limited correction (the external review's 2 HIGH +
1 MEDIUM-HIGH + the RESOLVING tightening; TASK-OPI-dc1bafdf…33 / the
opening ruling DEC-OPI-dc1bafdf…31 / VAL-OPI-dc1bafdf…35).

Migration 0036's ``action_replan`` (the durable replan obligation), the
``claim → work → complete`` consumption protocol
(:meth:`elc.world.scene.ScenePlanner.replan_scene` /
:meth:`elc.world.director.Director.apply_action_replan`), the
``outcome_ref`` chain (passage ← committed action + the targeted close +
the forced law), the span arm's two callers (NCP-2 ``close_scene=False``
/ NCP-3 ``close_scene=is_last_segment``), the RESOLVING-only door and
the one-gate law. The groups:

1. **migration 0036's shape** — ``action_replan``'s columns, the CHECK
   vocabularies, the ``UNIQUE (user_action_id)`` anchor, the composite
   ``APPLIED ⇒ target_ref`` CHECK, the stamps, and the table's place in
   ``GLOBAL_CONTENT_TABLES`` (this cut's 21-member tail append; V3-7's
   two tables extend the set to 23 at the same tail — the shared
   constants' head literal migrated the P9-1 way);
2. **the obligation's birth** — NCP-2's arm ⑧ lands the ``PENDING`` row
   in its own transaction for SCENE / CHAPTER rulings, zero rows for
   ``NONE``, and a replay births no second row;
3. **the consumption's idempotence** — the normal ``claim → work →
   complete`` paths (SCENE dossier ``max + 1``; CHAPTER revision, the
   matching ``PROPOSED`` residue reused), the ``APPLIED`` replay
   (zero-write, the same target) and the crash convergences (claim
   written then the work refused ⇒ the retry lands the same revision,
   never a second);
4. **the recovery survey's fifth family** — ``PENDING`` obligations
   listed, ``APPLIED`` ones not;
5. **the ``outcome_ref`` chain** — the passage's reference, the same
   transaction's targeted close, the three refusals, the forced law,
   the already-closed no-op and the replay's reference comparison;
6. **the span arm's two callers** — NCP-2 extends the scene's actual
   interval without closing it, NCP-3 continues it (and the last
   segment flips);
7. **the doors and the discipline** — the RESOLVING-only entry (the
   ``ANSWERED`` refusal naming ``begin_resolving``, the positive
   chain), the one-gate law across every non-``CLOSED`` word, the
   claim/complete helpers' shape keying, and the module scans (one
   BEGIN / one COMMIT per face; the targeted close).
"""

from __future__ import annotations

import ast
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from elc.platform.db.epoch import open_runtime_epoch
from elc.platform.db.migrations import apply_migrations
from elc.platform.types import DomainError, DomainErrorCode, Err, Ok
from elc.world.action import (
    ActionStatus,
    GateStatus,
    ReplanScope,
    ReplanStatus,
    action_of,
    begin_resolving,
    claim_replan_target,
    commit_action,
    get_gate,
    mark_replan_applied,
    pending_replans,
    recovery_scan,
    replan_obligation,
    replan_request_id_for,
    scene_of_action,
)
from elc.world.bible import SqliteBibleStore
from elc.world.cast import SqliteCastStore
from elc.world.director import Director
from elc.world.narrative import (
    PlanRevisionStatus,
    SceneStatus,
    SqliteNarrativeStore,
)
from elc.world.scene import ScenePlanner
from elc.world.store import SqliteWorldStore
from elc.world.writer import PovWriter
from tests.conftest import (
    MIGRATION_IDS,
    SCHEMA_HEAD_FILE,
    SCHEMA_HEAD_VERSION,
    SRC_ROOT,
)
from tests.world.test_v3_6_action import (
    GATE,
    LATER,
    NOW,
    SCENE,
    SCENE2,
    _active_scene,
    _blueprint,
    _chain,
    _commit,
    _committed_action,
    _gate,
    _rows,
    _ruling,
    _scene_draft,
    _submitted,
)

REPO = Path(__file__).resolve().parents[2]

ACTION_TREE = ast.parse(
    (SRC_ROOT / "world" / "action.py").read_text(encoding="utf-8")
)
SETTLEMENT_TREE = ast.parse(
    (SRC_ROOT / "world" / "settlement.py").read_text(encoding="utf-8")
)

# ---------------------------------------------------------------------------
# fixtures (the V3-6 suite's own shapes, verbatim)
# ---------------------------------------------------------------------------


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
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


@pytest.fixture()
def writer(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    narrative: SqliteNarrativeStore,
) -> PovWriter:
    return PovWriter(conn, narrative_store=narrative, world_store=world_store)


def _refuse(*args: Any, **kwargs: Any) -> Err[Any]:
    """One injected store refusal (the crash windows' tool)."""

    return Err(
        DomainError(
            code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
            message="injected failure",
        )
    )


def _chapter_fields(payload: dict[str, Any]) -> dict[str, Any]:
    """The eight chapter-side fields one plan revision carries (the
    payload minus ``scenes``) — the residue construction below spells
    exactly what the Director's creation would write."""

    return {
        key: payload[key]
        for key in (
            "goal",
            "dramatic_question",
            "planned_start_tick",
            "planned_end_tick",
            "closing_pressure",
            "desired_development",
            "soft_outcomes",
            "chapter_questions_to_advance",
        )
    }


def _sql_constants(tree: ast.AST) -> list[str]:
    """Every SQL-shaped string constant in one module."""

    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value.lstrip().upper().startswith(
                ("SELECT", "INSERT", "UPDATE", "DELETE")
            ):
                found.append(node.value)
    return found


def _all_constants(tree: ast.AST) -> list[str]:
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            found.append(node.value)
    return found


def _function(tree: ast.AST, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"function {name!r} not found")


# ---------------------------------------------------------------------------
# 1. migration 0036's shape
# ---------------------------------------------------------------------------


def test_action_replan_carries_its_columns_and_checks(
    conn: sqlite3.Connection,
) -> None:
    """``action_replan``'s physical column set, in order, the two
    vocabularies, the ``UNIQUE (user_action_id)`` anchor, the composite
    ``APPLIED ⇒ target_ref`` CHECK and the CAS floor — behaviourally
    (a PRAGMA cannot see CHECKs)."""

    columns = [
        (str(row[1]), str(row[2]), int(row[3]), int(row[5]))
        for row in conn.execute("PRAGMA table_info(action_replan)").fetchall()
    ]
    assert [(name, kind) for name, kind, *_ in columns] == [
        ("replan_request_id", "TEXT"),
        ("user_action_id", "TEXT"),
        ("scope", "TEXT"),
        ("status", "TEXT"),
        ("target_ref", "TEXT"),
        ("created_at", "TEXT"),
        ("updated_at", "TEXT"),
        ("state_version", "INTEGER"),
    ]
    assert columns[0][3] == 1  # replan_request_id is the primary key
    for name, _, not_null, _ in columns:
        if name == "target_ref":
            assert not_null == 0, name
        elif name == "replan_request_id":
            continue  # SQLite's notnull flag reads 0 on the TEXT PK
        else:
            assert not_null == 1, name

    # The minimal durable chain the FK needs: world → chapter → scene →
    # gate → action, then the obligation.
    conn.execute(
        "INSERT INTO world (world_id, name, template_world_id, created_at)"
        " VALUES ('w', 'W', NULL, ?)",
        (NOW,),
    )
    conn.execute(
        "INSERT INTO world_chapter ("
        " chapter_id, world_id, chapter_index, status, opened_at_tick,"
        " closed_at_tick, created_at, updated_at, state_version"
        ") VALUES ('w-ch01', 'w', 1, 'ACTIVE', 0, NULL, ?, ?, 1)",
        (NOW, NOW),
    )
    conn.execute(
        "INSERT INTO world_scene ("
        " scene_id, chapter_id, scene_index, status, actual_start_tick,"
        " actual_end_tick, created_at, updated_at, state_version"
        ") VALUES ('w-ch01-s01', 'w-ch01', 1, 'ACTIVE', NULL, NULL, ?, ?, 1)",
        (NOW, NOW),
    )
    conn.execute(
        "INSERT INTO user_gate ("
        " gate_id, scene_id, status, opened_at_tick, options_json,"
        " created_at, updated_at, state_version"
        ") VALUES ('g', 'w-ch01-s01', 'COMMITTED', 0, '[\"a\",\"b\"]', ?, ?, 1)",
        (NOW, NOW),
    )
    conn.execute(
        "INSERT INTO user_action ("
        " user_action_id, gate_id, submission_id, intent_text, status,"
        " created_at, updated_at, state_version"
        ") VALUES ('g-a', 'g', 'sub-1', 'intent', 'ANSWERED', ?, ?, 1)",
        (NOW, NOW),
    )
    conn.execute(
        "INSERT INTO action_replan ("
        " replan_request_id, user_action_id, scope, status, target_ref,"
        " created_at, updated_at, state_version"
        ") VALUES ('rp:g:sub-1', 'g-a', 'SCENE', 'PENDING', NULL, ?, ?, 1)",
        (NOW, NOW),
    )
    # The scope and the status vocabularies.
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "UPDATE action_replan SET scope = 'SAGA'"
            " WHERE replan_request_id = 'rp:g:sub-1'"
        )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "UPDATE action_replan SET status = 'DONE'"
            " WHERE replan_request_id = 'rp:g:sub-1'"
        )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "UPDATE action_replan SET state_version = 0"
            " WHERE replan_request_id = 'rp:g:sub-1'"
        )
    # One action, at most one obligation.
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO action_replan ("
            " replan_request_id, user_action_id, scope, status, target_ref,"
            " created_at, updated_at, state_version"
            ") VALUES ('rp:g:sub-2', 'g-a', 'CHAPTER', 'PENDING', NULL,"
            " ?, ?, 1)",
            (NOW, NOW),
        )
    # The composite CHECK: APPLIED is unwritable without a claim.
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "UPDATE action_replan SET status = 'APPLIED'"
            " WHERE replan_request_id = 'rp:g:sub-1'"
        )
    conn.execute(
        "UPDATE action_replan SET status = 'APPLIED', target_ref = 'w-ch01-s01-d2'"
        " WHERE replan_request_id = 'rp:g:sub-1'"
    )
    row = conn.execute(
        "SELECT scope, status, target_ref FROM action_replan"
        " WHERE replan_request_id = 'rp:g:sub-1'"
    ).fetchone()
    assert row == ("SCENE", "APPLIED", "w-ch01-s01-d2")
    # A dangling action is refused by the table's own FK.
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO action_replan ("
            " replan_request_id, user_action_id, scope, status, target_ref,"
            " created_at, updated_at, state_version"
            ") VALUES ('rp:x:sub-9', 'no-such-action', 'SCENE', 'PENDING',"
            " NULL, ?, ?, 1)",
            (NOW, NOW),
        )


def test_the_chain_head_and_the_ledger_membership() -> None:
    """The migration self-pin: the shared constants end at V3-7's
    ``0037_actor_memory_chapter_settlement`` / ``37`` (V3-6R's
    ``0036_action_replan`` / ``36`` was the head when this cut landed),
    a fresh database carries the table
    and the stamp, and the obligation joins the global keep set (this
    cut's 21-member tail append; V3-7's two tables extend the set to 23
    at the same tail)."""

    assert MIGRATION_IDS[-1] == "0037_actor_memory_chapter_settlement"
    assert MIGRATION_IDS[-2] == "0036_action_replan"
    assert MIGRATION_IDS[-3] == "0035_user_gate_action"
    assert SCHEMA_HEAD_FILE == "0037_actor_memory_chapter_settlement.sql"
    assert SCHEMA_HEAD_VERSION == "37"
    fresh = sqlite3.connect(":memory:")
    applied = apply_migrations(fresh)
    assert applied[-1] == "0037_actor_memory_chapter_settlement"
    stamps = dict(
        fresh.execute(
            "SELECT key, value FROM schema_meta"
            " WHERE key LIKE '%schema_version%'"
        ).fetchall()
    )
    assert stamps == {
        "schema_version": "37",
        "runtime_schema_version": "37",
    }
    tables = {
        str(row[0])
        for row in fresh.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    assert "action_replan" in tables

    from elc.deletion.types import GLOBAL_CONTENT_TABLES

    assert len(GLOBAL_CONTENT_TABLES) == 23
    assert "action_replan" in GLOBAL_CONTENT_TABLES
    assert GLOBAL_CONTENT_TABLES[-2:] == ("actor_memory", "chapter_settlement")


# ---------------------------------------------------------------------------
# 2. the obligation's birth (NCP-2's arm ⑧)
# ---------------------------------------------------------------------------


def test_ncp2_births_the_scene_obligation_in_its_own_transaction(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """``replan_scope = SCENE``: NCP-2's arm ⑧ lands the ``PENDING``
    obligation in the same short transaction — the derived
    ``replan_request_id``, the action's id, the scope word, an empty
    ``target_ref`` and the caller's clock."""

    _chain(
        conn,
        world_store,
        cast_store,
        bible_store,
        narrative,
        director,
        planner,
        adjudication=_ruling(replan_scope=ReplanScope.SCENE),
    )
    request_id = replan_request_id_for(GATE, "sub-1")
    assert request_id == f"rp:{GATE}:sub-1"
    obligation = replan_obligation(conn, request_id)
    assert obligation is not None
    assert obligation.replan_request_id == request_id
    assert obligation.user_action_id == f"{GATE}-a"
    assert obligation.scope is ReplanScope.SCENE
    assert obligation.status is ReplanStatus.PENDING
    assert obligation.target_ref is None
    assert obligation.created_at == LATER
    assert obligation.updated_at == LATER
    assert obligation.state_version == 1
    assert pending_replans(conn) == (obligation,)
    assert scene_of_action(conn, request_id) == SCENE


def test_ncp2_births_the_chapter_obligation_and_none_births_nothing(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The CHAPTER scope is the same birth; a ``NONE`` ruling leaves
    **zero rows** ("no obligation" is zero rows, not a word) — proven on
    a second scene's ruling beside the first scene's obligation."""

    scenes = [
        _scene_draft(purpose="first sight"),
        _scene_draft(purpose="the ledger"),
    ]
    _active_scene(
        conn,
        world_store,
        cast_store,
        bible_store,
        narrative,
        director,
        planner,
        scenes=scenes,
    )
    assert isinstance(planner.open_scene(SCENE2, NOW), Ok)

    assert isinstance(_gate(conn), Ok)
    assert isinstance(_submitted(conn), Ok)
    assert isinstance(
        _committed_action(
            conn,
            world_store,
            narrative,
            adjudication=_ruling(replan_scope=ReplanScope.CHAPTER),
        ),
        Ok,
    )
    request_id = replan_request_id_for(GATE, "sub-1")
    obligation = replan_obligation(conn, request_id)
    assert obligation is not None
    assert obligation.scope is ReplanScope.CHAPTER
    assert obligation.status is ReplanStatus.PENDING
    assert len(pending_replans(conn)) == 1

    # The NONE arm: scene 2's ruling births nothing.
    second_gate = f"{SCENE2}-g01"
    assert isinstance(_gate(conn, scene_id=SCENE2), Ok)
    assert isinstance(
        _submitted(conn, gate_id=second_gate, submission_id="sub-2"), Ok
    )
    landed = _committed_action(
        conn,
        world_store,
        narrative,
        gate_id=second_gate,
        submission_id="sub-2",
    )
    assert isinstance(landed, Ok)
    assert landed.value.replan_scope is ReplanScope.NONE
    assert (
        replan_obligation(
            conn, replan_request_id_for(second_gate, "sub-2")
        )
        is None
    )
    assert len(pending_replans(conn)) == 1  # the first scene's only
    assert _rows(conn, "SELECT COUNT(*) FROM action_replan")[0][0] == 1


def test_a_replayed_commit_births_no_second_obligation(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The replay arm answers first: the same-shape ``commit_action``
    replay touches the obligation never — one row, byte for byte."""

    _chain(
        conn,
        world_store,
        cast_store,
        bible_store,
        narrative,
        director,
        planner,
        adjudication=_ruling(replan_scope=ReplanScope.SCENE),
    )
    request_id = replan_request_id_for(GATE, "sub-1")
    born = replan_obligation(conn, request_id)
    replayed = _committed_action(
        conn,
        world_store,
        narrative,
        adjudication=_ruling(replan_scope=ReplanScope.SCENE),
    )
    assert isinstance(replayed, Ok)
    assert _rows(conn, "SELECT COUNT(*) FROM action_replan")[0][0] == 1
    assert replan_obligation(conn, request_id) == born


# ---------------------------------------------------------------------------
# 3. the consumption's idempotence (claim → work → complete)
# ---------------------------------------------------------------------------


def test_the_scene_replan_claims_works_and_completes(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The normal path: the claim writes ``target_ref`` before the plan
    change, the work mints ``max + 1`` and adopts it, the complete step
    discharges the obligation — and the ``APPLIED`` replay is a
    zero-write read of the same dossier."""

    _chain(
        conn,
        world_store,
        cast_store,
        bible_store,
        narrative,
        director,
        planner,
        adjudication=_ruling(replan_scope=ReplanScope.SCENE),
    )
    request_id = replan_request_id_for(GATE, "sub-1")
    element = _scene_draft(purpose="the ledger turns", must_hide="the iron key")
    first = planner.replan_scene(request_id, element, LATER)
    assert isinstance(first, Ok)
    assert first.value.dossier_id == f"{SCENE}-d2"
    assert first.value.status is PlanRevisionStatus.ADOPTED
    applied = replan_obligation(conn, request_id)
    assert applied is not None
    assert applied.status is ReplanStatus.APPLIED
    assert applied.target_ref == f"{SCENE}-d2"
    assert applied.updated_at == LATER
    assert applied.state_version == 3  # birth → claim → complete

    replayed = planner.replan_scene(
        request_id, element, "2026-10-13T00:00:00+00:00"
    )
    assert isinstance(replayed, Ok)
    assert replayed.value == first.value  # zero write, the same row
    assert [
        (d.dossier_revision, d.status)
        for d in narrative.dossiers_of(SCENE)
    ] == [
        (1, PlanRevisionStatus.SUPERSEDED),
        (2, PlanRevisionStatus.ADOPTED),
    ]


def test_the_scene_replan_converges_after_a_crash_between_claim_and_work(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The eager claim's whole point: with the work injected to fail,
    the obligation stands ``PENDING`` with ``target_ref`` already written
    — the retry rides the stored target and lands **the same** revision,
    never a second dossier."""

    _chain(
        conn,
        world_store,
        cast_store,
        bible_store,
        narrative,
        director,
        planner,
        adjudication=_ruling(replan_scope=ReplanScope.SCENE),
    )
    request_id = replan_request_id_for(GATE, "sub-1")
    element = _scene_draft(purpose="the ledger turns")
    monkeypatch.setattr(narrative, "create_dossier", _refuse)
    refused = planner.replan_scene(request_id, element, LATER)
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.DEPENDENCY_UNAVAILABLE
    assert refused.error.message == "injected failure"

    stuck = replan_obligation(conn, request_id)
    assert stuck is not None
    assert stuck.status is ReplanStatus.PENDING
    assert stuck.target_ref == f"{SCENE}-d2"
    assert [d.dossier_revision for d in narrative.dossiers_of(SCENE)] == [1]

    monkeypatch.undo()
    retried = planner.replan_scene(request_id, element, LATER)
    assert isinstance(retried, Ok)
    assert retried.value.dossier_id == f"{SCENE}-d2"
    dossiers = narrative.dossiers_of(SCENE)
    assert [d.dossier_id for d in dossiers] == [f"{SCENE}-d1", f"{SCENE}-d2"]
    assert dossiers[-1].status is PlanRevisionStatus.ADOPTED
    assert replan_obligation(conn, request_id).status is ReplanStatus.APPLIED  # type: ignore[union-attr]


def test_the_scene_replan_converges_after_a_crash_before_the_complete(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The crash after the work: the dossier landed ``ADOPTED`` while
    the obligation stands ``PENDING`` — the retry reuses the claimed row
    (no second create, no second adopt) and completes."""

    import elc.world.scene as scene_module

    _chain(
        conn,
        world_store,
        cast_store,
        bible_store,
        narrative,
        director,
        planner,
        adjudication=_ruling(replan_scope=ReplanScope.SCENE),
    )
    request_id = replan_request_id_for(GATE, "sub-1")
    element = _scene_draft(purpose="the ledger turns")
    monkeypatch.setattr(scene_module, "mark_replan_applied", _refuse)
    refused = planner.replan_scene(request_id, element, LATER)
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.DEPENDENCY_UNAVAILABLE
    stuck = replan_obligation(conn, request_id)
    assert stuck is not None
    assert stuck.status is ReplanStatus.PENDING
    assert stuck.target_ref == f"{SCENE}-d2"
    landed = narrative.get_dossier(f"{SCENE}-d2")
    assert landed is not None and landed.status is PlanRevisionStatus.ADOPTED

    monkeypatch.undo()
    retried = planner.replan_scene(request_id, element, LATER)
    assert isinstance(retried, Ok)
    assert retried.value.dossier_id == f"{SCENE}-d2"
    assert [
        (d.dossier_id, d.status) for d in narrative.dossiers_of(SCENE)
    ] == [
        (f"{SCENE}-d1", PlanRevisionStatus.SUPERSEDED),
        (f"{SCENE}-d2", PlanRevisionStatus.ADOPTED),
    ]
    assert replan_obligation(conn, request_id).status is ReplanStatus.APPLIED  # type: ignore[union-attr]


def test_the_scene_replan_resumes_a_created_proposed_revision(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The crash between create and adopt: the claimed revision exists
    ``PROPOSED`` while the obligation stands ``PENDING`` — the retry
    reuses the row (no second create) and adopts it."""

    _chain(
        conn,
        world_store,
        cast_store,
        bible_store,
        narrative,
        director,
        planner,
        adjudication=_ruling(replan_scope=ReplanScope.SCENE),
    )
    request_id = replan_request_id_for(GATE, "sub-1")
    element = _scene_draft(purpose="the ledger turns")
    monkeypatch.setattr(narrative, "adopt_dossier", _refuse)
    refused = planner.replan_scene(request_id, element, LATER)
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.DEPENDENCY_UNAVAILABLE
    created = narrative.get_dossier(f"{SCENE}-d2")
    assert created is not None
    assert created.status is PlanRevisionStatus.PROPOSED
    stuck = replan_obligation(conn, request_id)
    assert stuck is not None
    assert stuck.status is ReplanStatus.PENDING
    assert stuck.target_ref == f"{SCENE}-d2"

    monkeypatch.undo()
    retried = planner.replan_scene(request_id, element, LATER)
    assert isinstance(retried, Ok)
    assert retried.value.dossier_id == f"{SCENE}-d2"
    assert retried.value.status is PlanRevisionStatus.ADOPTED
    assert [
        (d.dossier_id, d.status) for d in narrative.dossiers_of(SCENE)
    ] == [
        (f"{SCENE}-d1", PlanRevisionStatus.SUPERSEDED),
        (f"{SCENE}-d2", PlanRevisionStatus.ADOPTED),
    ]
    assert replan_obligation(conn, request_id).status is ReplanStatus.APPLIED  # type: ignore[union-attr]


def test_the_chapter_replan_claims_works_and_completes(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The CHAPTER protocol: the claim writes the plan id, the work
    creates and adopts the next revision, the complete step discharges —
    and the ``APPLIED`` replay answers the claimed plan zero-write."""

    _chain(
        conn,
        world_store,
        cast_store,
        bible_store,
        narrative,
        director,
        planner,
        adjudication=_ruling(replan_scope=ReplanScope.CHAPTER),
    )
    request_id = replan_request_id_for(GATE, "sub-1")
    payload = _blueprint(
        scenes=[dict(_scene_draft(purpose="the ledger"), **{"scene_ref": 1})]
    )
    payload["scenes"][0]["place"] = "the flooded mill floor"
    first = director.apply_action_replan(request_id, payload, LATER)
    assert isinstance(first, Ok)
    assert first.value.plan.chapter_plan_id == "world-town-ch01-bp-r2"
    assert first.value.plan.status is PlanRevisionStatus.ADOPTED
    applied = replan_obligation(conn, request_id)
    assert applied is not None
    assert applied.status is ReplanStatus.APPLIED
    assert applied.target_ref == "world-town-ch01-bp-r2"
    assert [
        (p.plan_revision, p.status)
        for p in narrative.plans_of("world-town-ch01")
    ] == [
        (1, PlanRevisionStatus.SUPERSEDED),
        (2, PlanRevisionStatus.ADOPTED),
    ]

    replayed = director.apply_action_replan(
        request_id, payload, "2026-10-13T00:00:00+00:00"
    )
    assert isinstance(replayed, Ok)
    assert replayed.value == first.value
    assert len(narrative.plans_of("world-town-ch01")) == 2


def test_the_chapter_replan_resumes_a_matching_proposed_residue(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """revise_blueprint's residue law, read-only: the top revision still
    ``PROPOSED`` with this payload's shape is the crashed revise's
    residue — the target is that very revision (the resume-adopt path),
    never a revision minted beside it."""

    _chain(
        conn,
        world_store,
        cast_store,
        bible_store,
        narrative,
        director,
        planner,
        adjudication=_ruling(replan_scope=ReplanScope.CHAPTER),
    )
    request_id = replan_request_id_for(GATE, "sub-1")
    payload = _blueprint(
        scenes=[dict(_scene_draft(purpose="the ledger"), **{"scene_ref": 1})]
    )
    residue = narrative.create_plan(
        "world-town-ch01-bp-r2",
        "world-town-ch01",
        2,
        **_chapter_fields(payload),
        scenes=tuple(payload["scenes"]),
        now=NOW,
    )
    assert isinstance(residue, Ok)

    first = director.apply_action_replan(request_id, payload, LATER)
    assert isinstance(first, Ok)
    assert first.value.plan.chapter_plan_id == "world-town-ch01-bp-r2"
    assert first.value.plan.status is PlanRevisionStatus.ADOPTED
    assert [
        (p.plan_revision, p.status)
        for p in narrative.plans_of("world-town-ch01")
    ] == [
        (1, PlanRevisionStatus.SUPERSEDED),
        (2, PlanRevisionStatus.ADOPTED),
    ]
    applied = replan_obligation(conn, request_id)
    assert applied is not None and applied.target_ref == "world-town-ch01-bp-r2"


def test_the_chapter_replan_converges_after_a_crash_between_claim_and_work(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The chapter twin of the crash convergence: the claim stands, the
    work is refused — the retry rides the stored target and lands
    ``bp-r2`` once, never ``bp-r3`` beside it."""

    _chain(
        conn,
        world_store,
        cast_store,
        bible_store,
        narrative,
        director,
        planner,
        adjudication=_ruling(replan_scope=ReplanScope.CHAPTER),
    )
    request_id = replan_request_id_for(GATE, "sub-1")
    payload = _blueprint(
        scenes=[dict(_scene_draft(purpose="the ledger"), **{"scene_ref": 1})]
    )
    monkeypatch.setattr(narrative, "create_plan", _refuse)
    refused = director.apply_action_replan(request_id, payload, LATER)
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.DEPENDENCY_UNAVAILABLE
    stuck = replan_obligation(conn, request_id)
    assert stuck is not None
    assert stuck.status is ReplanStatus.PENDING
    assert stuck.target_ref == "world-town-ch01-bp-r2"

    monkeypatch.undo()
    retried = director.apply_action_replan(request_id, payload, LATER)
    assert isinstance(retried, Ok)
    assert retried.value.plan.chapter_plan_id == "world-town-ch01-bp-r2"
    assert [
        (p.plan_revision, p.status)
        for p in narrative.plans_of("world-town-ch01")
    ] == [
        (1, PlanRevisionStatus.SUPERSEDED),
        (2, PlanRevisionStatus.ADOPTED),
    ]
    assert replan_obligation(conn, request_id).status is ReplanStatus.APPLIED  # type: ignore[union-attr]


def test_the_two_consumers_refuse_each_others_scopes(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The scope key: a CHAPTER obligation is no SCENE face's to consume
    and the SCENE one is no Director face's — each ``VALIDATION_FAILED``
    naming the scope, nothing written."""

    _chain(
        conn,
        world_store,
        cast_store,
        bible_store,
        narrative,
        director,
        planner,
        adjudication=_ruling(replan_scope=ReplanScope.CHAPTER),
    )
    chapter_request = replan_request_id_for(GATE, "sub-1")
    wrong = planner.replan_scene(chapter_request, _scene_draft(), LATER)
    assert isinstance(wrong, Err)
    assert wrong.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "SCENE obligations only" in wrong.error.message

    missing = director.apply_action_replan(
        "rp:no-such-gate:sub-0", _blueprint(), LATER
    )
    assert isinstance(missing, Err)
    assert missing.error.code is DomainErrorCode.NOT_FOUND


# ---------------------------------------------------------------------------
# 4. the recovery survey's fifth family
# ---------------------------------------------------------------------------


def test_the_recovery_scan_lists_pending_obligations_and_drops_applied(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """RA §29's fifth family: a ``PENDING`` obligation appears in the
    survey (``replans``) — and only there; once discharged it is
    history, not an error."""

    _chain(
        conn,
        world_store,
        cast_store,
        bible_store,
        narrative,
        director,
        planner,
        adjudication=_ruling(replan_scope=ReplanScope.SCENE),
    )
    request_id = replan_request_id_for(GATE, "sub-1")
    scan = recovery_scan(conn, narrative_store=narrative)
    assert isinstance(scan, Ok)
    assert [r.replan_request_id for r in scan.value.replans] == [request_id]
    assert scan.value.replans[0].status is ReplanStatus.PENDING

    consumed = planner.replan_scene(request_id, _scene_draft(), LATER)
    assert isinstance(consumed, Ok)
    after = recovery_scan(conn, narrative_store=narrative)
    assert isinstance(after, Ok)
    assert after.value.replans == ()
    assert pending_replans(conn) == ()


# ---------------------------------------------------------------------------
# 5. the outcome_ref chain
# ---------------------------------------------------------------------------


def test_the_reference_lands_and_closes_the_gate_in_one_transaction(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The physical chain: ``narrative_passage.outcome_ref`` carries the
    action id, the referenced gate moves ``COMMITTED → CLOSED``, and an
    injected failure after the tick rolls **the whole group** back — the
    passage, the reference and the close are one transaction's."""

    import elc.world.settlement as settlement_module

    _chain(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    monkeypatch.setattr(settlement_module, "advance_current_tick", _refuse)
    refused = _commit(
        conn,
        narrative,
        world_store,
        now=LATER,
        outcome_ref=f"{GATE}-a",
        duration_ticks=1,
    )
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.DEPENDENCY_UNAVAILABLE
    assert _rows(conn, "SELECT COUNT(*) FROM narrative_passage")[0][0] == 0
    assert get_gate(conn, GATE).status is GateStatus.COMMITTED  # type: ignore[union-attr]
    assert _rows(conn, "SELECT current_tick FROM world")[0][0] == 7

    monkeypatch.undo()
    landed = _commit(
        conn,
        narrative,
        world_store,
        now=LATER,
        outcome_ref=f"{GATE}-a",
        duration_ticks=1,
    )
    assert isinstance(landed, Ok)
    assert _rows(
        conn, "SELECT outcome_ref FROM narrative_passage"
    ) == [(f"{GATE}-a",)]
    closed = get_gate(conn, GATE)
    assert closed is not None
    assert closed.status is GateStatus.CLOSED
    assert closed.state_version == 5  # OPEN→ANSWERED→RESOLVING→COMMITTED→CLOSED
    assert landed.value.actual_end_tick == 8


def test_the_reference_refusals_are_three(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """A dangling reference is ``NOT_FOUND``; a reference to an
    uncommitted ruling, and a reference to another scene's ruling, are
    ``VALIDATION_FAILED`` — each before a single row lands."""

    scenes = [
        _scene_draft(purpose="first sight"),
        _scene_draft(purpose="the ledger"),
    ]
    _active_scene(
        conn,
        world_store,
        cast_store,
        bible_store,
        narrative,
        director,
        planner,
        scenes=scenes,
    )
    assert isinstance(planner.open_scene(SCENE2, NOW), Ok)

    dangling = _commit(
        conn, narrative, world_store, now=LATER, outcome_ref="no-such-action"
    )
    assert isinstance(dangling, Err)
    assert dangling.error.code is DomainErrorCode.NOT_FOUND
    assert "names no user action" in dangling.error.message

    # Scene 2's submission exists but has not passed the resolver.
    assert isinstance(_gate(conn, scene_id=SCENE2), Ok)
    assert isinstance(
        _submitted(conn, gate_id=f"{SCENE2}-g01", submission_id="sub-2"), Ok
    )
    uncommitted = _commit(
        conn,
        narrative,
        world_store,
        now=LATER,
        outcome_ref=f"{SCENE2}-g01-a",
    )
    assert isinstance(uncommitted, Err)
    assert uncommitted.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "only a COMMITTED ruling is resumed" in uncommitted.error.message

    # Commit it, then use a *foreign scene's* committed ruling on scene 1.
    assert isinstance(
        _committed_action(
            conn,
            world_store,
            narrative,
            gate_id=f"{SCENE2}-g01",
            submission_id="sub-2",
        ),
        Ok,
    )
    foreign = _commit(
        conn,
        narrative,
        world_store,
        now=LATER,
        outcome_ref=f"{SCENE2}-g01-a",
    )
    assert isinstance(foreign, Err)
    assert foreign.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "passage resumes the ruling of its own scene" in foreign.error.message

    # Scene 1's own ruling, however, is no ruling at all (its gate was
    # never opened) — the positive control lives in the neighbouring
    # tests; here the three refusals left zero passages.
    assert _rows(conn, "SELECT COUNT(*) FROM narrative_passage")[0][0] == 0


def test_the_forced_law_and_the_targeted_close(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The forced law (a committed gate demands the resuming segment's
    reference) and the targeted close: the segment closes **its** gate
    and leaves another scene's committed gate standing (the V3-6
    blanket close is gone)."""

    scenes = [
        _scene_draft(purpose="first sight"),
        _scene_draft(purpose="the ledger"),
    ]
    _active_scene(
        conn,
        world_store,
        cast_store,
        bible_store,
        narrative,
        director,
        planner,
        scenes=scenes,
    )
    assert isinstance(planner.open_scene(SCENE2, NOW), Ok)
    assert isinstance(_gate(conn), Ok)
    assert isinstance(_submitted(conn), Ok)
    assert isinstance(_committed_action(conn, world_store, narrative), Ok)
    gate_two = f"{SCENE2}-g01"
    assert isinstance(_gate(conn, scene_id=SCENE2), Ok)
    assert isinstance(
        _submitted(conn, gate_id=gate_two, submission_id="sub-2"), Ok
    )
    assert isinstance(
        _committed_action(
            conn,
            world_store,
            narrative,
            gate_id=gate_two,
            submission_id="sub-2",
        ),
        Ok,
    )
    assert get_gate(conn, gate_two).status is GateStatus.COMMITTED  # type: ignore[union-attr]
    gate_two_version = get_gate(conn, gate_two).state_version  # type: ignore[union-attr]

    missing = _commit(conn, narrative, world_store, now=LATER)
    assert isinstance(missing, Err)
    assert missing.error.code is DomainErrorCode.VALIDATION_FAILED
    assert f"{GATE}-a" in missing.error.message
    assert "outcome_ref" in missing.error.message

    resumed = _commit(
        conn, narrative, world_store, now=LATER, outcome_ref=f"{GATE}-a"
    )
    assert isinstance(resumed, Ok)
    assert get_gate(conn, GATE).status is GateStatus.CLOSED  # type: ignore[union-attr]
    still = get_gate(conn, gate_two)
    assert still is not None
    assert still.status is GateStatus.COMMITTED
    assert still.state_version == gate_two_version  # untouched by the close


def test_a_replay_with_a_different_reference_conflicts(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The replay's shape includes the reference: the same segment key
    with the same reference rides back as a no-op, a different one is
    the dedicated ``CONFLICT`` sentence."""

    _chain(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    first = _commit(
        conn, narrative, world_store, now=LATER, outcome_ref=f"{GATE}-a"
    )
    assert isinstance(first, Ok)
    replayed = _commit(
        conn,
        narrative,
        world_store,
        now="2026-10-13T00:00:00+00:00",
        outcome_ref=f"{GATE}-a",
    )
    assert isinstance(replayed, Ok)
    assert replayed.value == first.value
    assert _rows(conn, "SELECT COUNT(*) FROM narrative_passage")[0][0] == 1

    # A second committed ruling on the scene (the first gate is closed).
    gate_two = f"{SCENE}-g02"
    assert isinstance(_gate(conn, gate_seq=2, now=LATER), Ok)
    assert isinstance(
        _submitted(conn, gate_id=gate_two, submission_id="sub-2", now=LATER),
        Ok,
    )
    assert isinstance(
        _committed_action(
            conn,
            world_store,
            narrative,
            gate_id=gate_two,
            submission_id="sub-2",
        ),
        Ok,
    )
    conflicted = _commit(
        conn,
        narrative,
        world_store,
        now=LATER,
        outcome_ref=f"{gate_two}-a",
    )
    assert isinstance(conflicted, Err)
    assert conflicted.error.code is DomainErrorCode.CONFLICT
    assert "different outcome_ref" in conflicted.error.message


def test_an_already_closed_reference_is_a_no_op(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """A second segment may carry the same reference again: the gate is
    already ``CLOSED``, so the close answers a zero-row UPDATE — the
    gate's version does not move, and the reference still lands."""

    _chain(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    first = _commit(
        conn, narrative, world_store, now=LATER, outcome_ref=f"{GATE}-a"
    )
    assert isinstance(first, Ok)
    closed = get_gate(conn, GATE)
    assert closed is not None and closed.status is GateStatus.CLOSED
    second = _commit(
        conn,
        narrative,
        world_store,
        segment_seq=2,
        now=LATER,
        outcome_ref=f"{GATE}-a",
    )
    assert isinstance(second, Ok)
    assert _rows(
        conn,
        "SELECT outcome_ref FROM narrative_passage ORDER BY segment_seq",
    ) == [(f"{GATE}-a",), (f"{GATE}-a",)]
    after = get_gate(conn, GATE)
    assert after is not None
    assert after.status is GateStatus.CLOSED
    assert after.state_version == closed.state_version  # zero-row UPDATE


# ---------------------------------------------------------------------------
# 6. the span arm's two callers
# ---------------------------------------------------------------------------


def test_ncp2_extends_the_scene_span_without_closing_it(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The V3-6R span law's NCP-2 caller: the action extends the scene's
    actual interval (start via ``COALESCE``, end to the post-advance
    tick) and never flips it — ``close_scene=False``."""

    _chain(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    scene = narrative.get_scene(SCENE)
    assert scene is not None
    assert (scene.actual_start_tick, scene.actual_end_tick) == (0, 7)
    assert scene.status is SceneStatus.ACTIVE
    assert scene.state_version == 3  # mint → activate → span


def test_ncp3_continues_the_span_the_action_opened(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The two callers share one UPDATE: the action opens the span
    (0 → 7), the segment continues it (7 → 8, ``COALESCE`` keeps 0), and
    the last segment carries the flip — four version bumps in all."""

    _chain(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    continued = _commit(
        conn,
        narrative,
        world_store,
        now=LATER,
        duration_ticks=1,
        outcome_ref=f"{GATE}-a",
    )
    assert isinstance(continued, Ok)
    scene = narrative.get_scene(SCENE)
    assert scene is not None
    assert (scene.actual_start_tick, scene.actual_end_tick) == (0, 8)
    assert scene.status is SceneStatus.ACTIVE
    assert scene.state_version == 4

    last = _commit(
        conn,
        narrative,
        world_store,
        segment_seq=2,
        now=LATER,
        duration_ticks=2,
        is_last_segment=True,
    )
    assert isinstance(last, Ok)
    assert last.value.scene_committed is True
    settled = narrative.get_scene(SCENE)
    assert settled is not None
    assert (settled.actual_start_tick, settled.actual_end_tick) == (0, 10)
    assert settled.status is SceneStatus.COMMITTED
    assert settled.state_version == 5


# ---------------------------------------------------------------------------
# 7. the doors and the discipline
# ---------------------------------------------------------------------------


def test_commit_action_refuses_before_begin_resolving(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The RESOLVING-only door: an ``ANSWERED`` pair refuses the ruling
    ``VALIDATION_FAILED`` naming ``begin_resolving`` (nothing written);
    the ``begin_resolving → commit_action`` chain is the one main
    path."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    assert isinstance(_gate(conn), Ok)
    assert isinstance(_submitted(conn), Ok)
    direct = commit_action(
        conn,
        world_store=world_store,
        narrative_store=narrative,
        gate_id=GATE,
        submission_id="sub-1",
        adjudication=_ruling(),
        duration_ticks=7,
        now=LATER,
    )
    assert isinstance(direct, Err)
    assert direct.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "begin_resolving" in direct.error.message
    stuck = action_of(conn, GATE)
    assert stuck is not None and stuck.status is ActionStatus.ANSWERED
    assert _rows(conn, "SELECT COUNT(*) FROM world_event")[0][0] == 0
    assert _rows(conn, "SELECT current_tick FROM world")[0][0] == 0

    moved = begin_resolving(conn, gate_id=GATE, now=LATER)
    assert isinstance(moved, Ok)
    again = begin_resolving(conn, gate_id=GATE, now=LATER)
    assert isinstance(again, Ok)
    assert again.value == moved.value  # idempotent
    landed = commit_action(
        conn,
        world_store=world_store,
        narrative_store=narrative,
        gate_id=GATE,
        submission_id="sub-1",
        adjudication=_ruling(),
        duration_ticks=7,
        now=LATER,
    )
    assert isinstance(landed, Ok)
    assert landed.value.actual_end_tick == 7


def test_the_one_gate_law_walks_the_whole_lifecycle(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The one-gate law: ``OPEN`` / ``ANSWERED`` / ``RESOLVING`` /
    ``COMMITTED`` all refuse a second gate — and a ``CLOSED`` one (a
    continuing segment carrying its reference) frees the scene."""

    _chain(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    refused = _gate(conn, gate_seq=2, now=LATER)
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "standing gate" in refused.error.message
    assert "close the previous gate" in refused.error.message

    resumed = _commit(
        conn, narrative, world_store, now=LATER, outcome_ref=f"{GATE}-a"
    )
    assert isinstance(resumed, Ok)
    assert get_gate(conn, GATE).status is GateStatus.CLOSED  # type: ignore[union-attr]
    opened = _gate(conn, gate_seq=2, now=LATER)
    assert isinstance(opened, Ok)
    assert opened.value.gate_id == f"{SCENE}-g02"

    # The remaining lifecycle words refuse too (OPEN / ANSWERED /
    # RESOLVING on the new gate, one word at a time).
    third = _gate(conn, gate_seq=3, now=LATER)
    assert isinstance(third, Err)
    assert third.error.code is DomainErrorCode.VALIDATION_FAILED
    second_gate = f"{SCENE}-g02"
    assert isinstance(
        _submitted(conn, gate_id=second_gate, submission_id="sub-2", now=LATER),
        Ok,
    )
    third = _gate(conn, gate_seq=3, now=LATER)
    assert isinstance(third, Err)
    assert third.error.code is DomainErrorCode.VALIDATION_FAILED
    assert isinstance(begin_resolving(conn, gate_id=second_gate, now=LATER), Ok)
    third = _gate(conn, gate_seq=3, now=LATER)
    assert isinstance(third, Err)
    assert third.error.code is DomainErrorCode.VALIDATION_FAILED


def test_the_claim_and_complete_helpers_are_shape_keyed(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The helpers' own refusals: a missing obligation is ``NOT_FOUND``;
    the complete step without a claim is ``VALIDATION_FAILED``; the same
    claim is a zero-write ``Ok``; a different one is ``CONFLICT``; an
    ``APPLIED`` obligation answers its stored row to both."""

    _chain(
        conn,
        world_store,
        cast_store,
        bible_store,
        narrative,
        director,
        planner,
        adjudication=_ruling(replan_scope=ReplanScope.SCENE),
    )
    request_id = replan_request_id_for(GATE, "sub-1")
    missing = claim_replan_target(
        conn,
        replan_request_id="rp:no-such:sub-0",
        target_ref="x",
        now=LATER,
    )
    assert isinstance(missing, Err)
    assert missing.error.code is DomainErrorCode.NOT_FOUND

    unclaimed = mark_replan_applied(conn, replan_request_id=request_id, now=LATER)
    assert isinstance(unclaimed, Err)
    assert unclaimed.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "no claim stands" in unclaimed.error.message

    blank = claim_replan_target(
        conn, replan_request_id=request_id, target_ref="   ", now=LATER
    )
    assert isinstance(blank, Err)
    assert blank.error.code is DomainErrorCode.VALIDATION_FAILED

    claimed = claim_replan_target(
        conn,
        replan_request_id=request_id,
        target_ref=f"{SCENE}-d2",
        now=LATER,
    )
    assert isinstance(claimed, Ok)
    assert claimed.value.target_ref == f"{SCENE}-d2"
    assert claimed.value.state_version == 2
    same = claim_replan_target(
        conn,
        replan_request_id=request_id,
        target_ref=f"{SCENE}-d2",
        now="2026-10-13T00:00:00+00:00",
    )
    assert isinstance(same, Ok)
    assert same.value == claimed.value  # zero write
    different = claim_replan_target(
        conn,
        replan_request_id=request_id,
        target_ref=f"{SCENE}-d3",
        now=LATER,
    )
    assert isinstance(different, Err)
    assert different.error.code is DomainErrorCode.CONFLICT
    assert "does not rewrite" in different.error.message

    applied = mark_replan_applied(conn, replan_request_id=request_id, now=LATER)
    assert isinstance(applied, Ok)
    assert applied.value.status is ReplanStatus.APPLIED
    assert applied.value.updated_at == LATER
    again = mark_replan_applied(
        conn, replan_request_id=request_id, now="2026-10-13T00:00:00+00:00"
    )
    assert isinstance(again, Ok)
    assert again.value == applied.value  # idempotent zero write
    re_claimed = claim_replan_target(
        conn,
        replan_request_id=request_id,
        target_ref=f"{SCENE}-d2",
        now="2026-10-13T00:00:00+00:00",
    )
    assert isinstance(re_claimed, Ok)
    assert re_claimed.value == applied.value  # the APPLIED row rides back


def test_the_new_faces_are_one_transaction_and_the_close_targeted() -> None:
    """The discipline scans: each new helper opens exactly one ``BEGIN
    IMMEDIATE`` and lands exactly one ``COMMIT`` (its ``_tx`` body
    carries no transaction control at all), and the settlement's close
    UPDATE is **targeted by ``gate_id``** — the V3-6 blanket close's
    shape is gone."""

    for name in ("claim_replan_target", "mark_replan_applied"):
        public = _function(ACTION_TREE, name)
        constants = _all_constants(public)
        assert constants.count("BEGIN IMMEDIATE") == 1, name
        assert constants.count("COMMIT") == 1, name
    for name in ("_claim_replan_target_tx", "_mark_replan_applied_tx"):
        body = _function(ACTION_TREE, name)
        assert _sql_constants(body), (name, "the body carries no SQL")
        for text in _all_constants(body):
            assert text != "BEGIN IMMEDIATE", (name, text)
            assert text != "COMMIT", (name, text)
            assert text != "ROLLBACK", (name, text)
    for node in ast.walk(ACTION_TREE):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in {"commit", "rollback"}, node.func.attr

    body = _function(SETTLEMENT_TREE, "_commit_segment_tx")
    closes = [
        text
        for text in _sql_constants(body)
        if text.lstrip().upper().startswith("UPDATE USER_GATE")
    ]
    assert len(closes) == 1, closes
    assert "CLOSED" in closes[0]
    assert "gate_id = ?" in closes[0]
    assert "scene_id" not in closes[0]
