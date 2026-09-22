"""P6-3 ③.6 — the invariants this cut must not break, and what it deliberately
did not wire.

Four kinds of claim live here:

- **``scope`` is carried, never interpreted**: the store and the authority
  face branch on no scope word, declare no semantics for one, and the module
  that would have to answer "which session is current?" says so instead of
  guessing (R7's registration);
- **nothing consumes a constraint**: no Planner reads the table, the Gate is
  not wired to it, and the set of source files that mention the object is
  exactly the placement plus the two pre-existing mentions (R11's red line,
  made checkable);
- **the row has no store-stamped column**: the two writes go through with the
  store's clock disabled, so nothing in the row can be a clock reading;
- **the registry entry is the placement**, and the Gate's five categories
  (seven keys) are unchanged.

The suite-level red lines (no ``_seed``, no fixture supply, nothing skipped,
cold-start imports) are the P6-1 self-pins' and cover these files too, since
they scan the whole phase-6 directory.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

from elc.platform.registry import (
    CANONICAL_OBJECTS,
    OWNER_USER_CONFIG,
)
from elc.platform.types import Ok
from elc.teaching.gate import TARGET_SUPPRESSED_NO_SOURCE
from elc.user_config import store as store_module
from elc.user_config.store import SqliteUserConfigStore
from elc.user_config.types import PLANNER_CONSTRAINT_SCOPES
from tests.conftest import REPO_ROOT, SRC_ROOT

from .conftest import CONSTRAINT_ID, planner_constraint

STORE_PATH = SRC_ROOT / "user_config" / "store.py"
CONTROLLER_PATH = SRC_ROOT / "user_config" / "controller.py"

#: The five modules the P6-3 cut touches, for the word scans below.
P6_3_MODULES = (
    STORE_PATH,
    CONTROLLER_PATH,
    SRC_ROOT / "user_config" / "types.py",
    SRC_ROOT / "user_config" / "commands.py",
    SRC_ROOT / "user_config" / "queries.py",
)

#: Gate item 5's seven categories and their registry keys
#: (docs/DOMAIN_MODEL.md §2 Authority Matrix) — P6-3 adds a key, not a
#: category, so this mapping is untouched.
GATE_CATEGORY_KEYS = {
    "Goal": "goal_portfolio",
    "Policy": "teaching_policy",
    "Profile": "user_profile",
    "Scheduler": "schedule_view",
    "Gate": "gate_decision",
    "Validator": "validator_result",
    "Projection": "projection_job",
}


def _code_only(source: str) -> str:
    """The module's executable text: docstrings blanked, comments dropped.

    A scan for a forbidden *use* must not be defeated by the prose that
    explains why the use is absent — this cut's modules name ``scope`` and
    ``THIS_SESSION`` precisely to say they do not interpret them (the p6-1
    lesson: "the word appears nowhere" is the wrong pin, so the word is looked
    for where a use would have to be written).
    """

    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(
            node,
            (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
        ):
            continue
        body = node.body
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            body[0].value.value = ""
    return ast.unparse(tree)


# -- ① scope is carried, never interpreted -----------------------------------


def _replay_equality_node(tree: ast.Module) -> ast.FunctionDef:
    """The one helper that compares ``scope`` — and why it may.

    ``_same_constraint`` asks "is this the same durable content?", which is a
    byte-for-byte comparison of every §9 column (the append-first replay
    rule). That is identity, not meaning: the pin below is about *decisions
    taken from a scope's value*, and comparing two spellings for equality is
    like comparing ``starts_at`` for equality — it says nothing about what
    THIS_SESSION means.
    """

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_same_constraint":
            return node
    raise AssertionError("_same_constraint is gone; revisit this pin")


def test_the_store_branches_on_no_scope() -> None:
    """No comparison outside the replay-equality helper mentions ``scope``:
    the column is decoded into the enum and travels out, and no read face
    decides anything from it (R7). A ``scope`` predicate that decides
    membership, a window or a lifecycle would have to be written as one of
    these comparisons, and there is none."""

    tree = ast.parse(STORE_PATH.read_text(encoding="utf-8"))
    ignored = {
        id(node)
        for node in ast.walk(_replay_equality_node(tree))
    }
    for node in ast.walk(tree):
        if id(node) in ignored:
            continue
        if not isinstance(node, ast.Compare):
            continue
        for side in [node.left, *node.comparators]:
            if isinstance(side, ast.Attribute) and side.attr == "scope":
                raise AssertionError(
                    f"a comparison reads .scope: {ast.dump(node)[:80]}"
                )
            if isinstance(side, ast.Name) and side.id == "scope":
                raise AssertionError(
                    f"a comparison reads scope: {ast.dump(node)[:80]}"
                )


def test_no_scope_word_appears_in_the_stores_executable_text() -> None:
    """None of the three words is written in code: a scope predicate would
    have to spell one of them, and there is none."""

    code = _code_only(STORE_PATH.read_text(encoding="utf-8"))
    for word in PLANNER_CONSTRAINT_SCOPES:
        assert word not in code, word


def test_the_controller_branches_on_no_scope() -> None:
    source = CONTROLLER_PATH.read_text(encoding="utf-8")
    assert ".scope ==" not in source
    code = _code_only(source)
    for word in PLANNER_CONSTRAINT_SCOPES:
        assert word not in code, word


def test_the_scope_column_is_decoded_but_not_judged() -> None:
    """The one legitimate use — the decode — is still there, and it is the only
    *call* the enum has in the store's executable text: the read faces hand
    back the enum so a consumer never compares raw strings, and no face asks
    what the word means."""

    code = " ".join(_code_only(STORE_PATH.read_text(encoding="utf-8")).split())
    assert "PlannerConstraintScope(str(row[4]))" in code
    assert code.count("PlannerConstraintScope(") == 1


def test_the_store_registers_the_session_reading_it_does_not_take() -> None:
    """``THIS_SESSION`` names a session and §9 gives the object no conversation
    column, so the module that would have to answer says so where the read
    faces are declared — and names the revisit condition."""

    docstring = " ".join(
        (store_module.__doc__ or "").replace("``", "").split()
    )
    for phrase in (
        "carried, never interpreted",
        "THIS_SESSION",
        "no conversation column",
        "Revisit condition",
        "PlannerConstraintView",
    ):
        assert phrase in docstring, phrase


# -- ② nothing consumes a constraint -----------------------------------------


def test_the_object_is_mentioned_by_the_placement_and_two_pre_existing_modules(
) -> None:
    """R11's red line, made checkable: P6-3 wired the object into nothing. The
    files that mention it are the placement (six user_config modules plus the
    registry) and the two mentions that predate this cut — the Phase 0
    ``PlannerDecision.planner_constraint_view`` field and the Gate's comment
    naming §9 as the future suppression source. A further file would be a
    consumer nobody reviewed.

    Gate 2 added ``deletion/store.py``, and it is **not** a consumer: it is
    the module that clears the constraint's ``created_from_turn_id`` leg when
    the turn it names is deleted (§19). The compensation below holds that
    apart — the deletion face names the table and touches one provenance
    column, never the user's setting or its ``active`` flag.
    """

    mentioning = sorted(
        path.relative_to(SRC_ROOT).as_posix()
        for path in SRC_ROOT.rglob("*.py")
        if "planner_constraint" in path.read_text(encoding="utf-8").lower()
        or "PlannerConstraint" in path.read_text(encoding="utf-8")
    )
    assert mentioning == [
        "deletion/store.py",
        "deletion/types.py",
        "planner/types.py",
        "platform/registry.py",
        "teaching/gate.py",
        "user_config/__init__.py",
        "user_config/commands.py",
        "user_config/controller.py",
        "user_config/queries.py",
        "user_config/store.py",
        "user_config/types.py",
    ]

    # Prose may name the object; only *statements* are constrained, and there
    # are exactly three of them: the surface select, the row delete, and the
    # one provenance-leg clear. Anything else — an insert, a second update, a
    # read of ``active`` — would be the unreviewed consumer R11 forbids.
    deletion_source = (SRC_ROOT / "deletion" / "store.py").read_text(
        encoding="utf-8"
    )
    assert "SELECT rowid, constraint_id FROM planner_constraint" in (
        deletion_source
    )
    assert "DELETE FROM planner_constraint" in deletion_source
    assert "INSERT INTO planner_constraint" not in deletion_source
    assert deletion_source.count("UPDATE planner_constraint") == 1
    assert (
        "UPDATE planner_constraint SET created_from_turn_id = NULL"
        in deletion_source
    )
    for column in ("active", "constraint_type", "scope", "starts_at"):
        assert f"SET {column}" not in deletion_source, column


def test_the_gate_is_still_not_wired_to_a_constraint() -> None:
    """The Gate's suppression fact keeps its NO_SOURCE value, and the Gate
    imports nothing from this context: P6-3 lands durable truth, not an
    applied effect (R11). Its docstring's "tables that do not exist yet" is
    the next cut's to revisit — the behaviour below is what this cut pins."""

    assert TARGET_SUPPRESSED_NO_SOURCE is False
    source = (SRC_ROOT / "teaching" / "gate.py").read_text(encoding="utf-8")
    assert "user_config" not in source
    assert "planner_constraint" not in source


def test_no_p6_3_module_carries_a_phase_pointer() -> None:
    """Every face this cut declares is implemented: no module of the five
    raises a phase pointer or carries the red-line constant any more."""

    for path in P6_3_MODULES:
        source = path.read_text(encoding="utf-8")
        assert "NotImplementedError" not in source, path.name
        assert "P6_3_CONSTRAINT_POINTER" not in source, path.name


def test_no_p6_3_module_carries_a_distributed_primitive() -> None:
    """Local V1's permanent prohibition (RA §24.1), re-checked over the files
    this cut touches."""

    for path in P6_3_MODULES:
        lowered = path.read_text(encoding="utf-8").lower()
        for word in ("lease", "heartbeat", "expire_after", "distributed_lock"):
            assert word not in lowered, f"{path.name}: {word}"


# -- ③ the row has no store-stamped column -----------------------------------


def test_the_writes_go_through_with_the_stores_clock_disabled(
    db, user_config_store: SqliteUserConfigStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§9's object carries no store-stamped column (the SessionFocus shape), so
    a constraint can be written and its flag transferred while the store's own
    clock is a landmine — nothing in either path may read it."""

    def _forbidden() -> str:  # pragma: no cover - it must never be called
        raise AssertionError("a constraint row reads no clock")

    monkeypatch.setattr(store_module, "_now", _forbidden)
    written = planner_constraint()
    assert isinstance(user_config_store.record_planner_constraint(written), Ok)
    moved = user_config_store.set_planner_constraint_active(CONSTRAINT_ID, False)
    assert isinstance(moved, Ok), moved
    assert moved.value.active is False
    assert db.execute("SELECT active FROM planner_constraint").fetchone() == (
        0,
    )


def test_the_constraint_table_has_no_clock_column(db) -> None:
    """The same claim in the schema: none of §9's nine columns is a store
    timestamp (``starts_at`` / ``expires_at`` are the caller's declarations)."""

    columns = [
        str(row[1])
        for row in db.execute("PRAGMA table_info(planner_constraint)")
    ]
    assert columns == [
        "constraint_id",
        "target_type",
        "target_id",
        "constraint_type",
        "scope",
        "starts_at",
        "expires_at",
        "created_from_turn_id",
        "active",
    ]
    assert not [
        column
        for column in columns
        if column.endswith(("_at", "_timestamp"))
        and column not in ("starts_at", "expires_at")
    ]


# -- ④ the registry and the Gate categories ----------------------------------


def test_the_registry_entry_is_the_placement() -> None:
    assert "planner_constraint" in CANONICAL_OBJECTS
    entry = CANONICAL_OBJECTS["planner_constraint"]
    assert entry.owner == OWNER_USER_CONFIG
    assert entry.schema.__name__ == "PlannerConstraint"
    assert entry.schema.__module__ == "elc.user_config.types"


def test_the_registry_entry_binds_no_version_field() -> None:
    """§9 pins no version column on this object, so a binding would claim a
    canonical spelling that does not exist (the ScheduleItem rule)."""

    assert CANONICAL_OBJECTS["planner_constraint"].version_field is None


def test_the_gate_five_categories_are_unchanged() -> None:
    """P6-3 adds a registry key for a new canonical object; Gate item 5's seven
    parent categories are exactly what they were."""

    for category, key in GATE_CATEGORY_KEYS.items():
        assert key in CANONICAL_OBJECTS, category
        assert CANONICAL_OBJECTS[key].owner, category


def test_the_owner_is_a_real_package() -> None:
    assert (SRC_ROOT / OWNER_USER_CONFIG).is_dir()


# -- ⑤ cold start -------------------------------------------------------------


def test_the_new_faces_import_from_a_cold_interpreter() -> None:
    """The P4-3 lesson at its strongest: a fresh interpreter importing the new
    declarations first must succeed (an import cycle can hide behind a lucky
    test-session order)."""

    env = dict(
        os.environ,
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=str(Path(REPO_ROOT) / "src"),
    )
    for statement in (
        "from elc.user_config.types import PlannerConstraint",
        "from elc.user_config.types import PlannerConstraintType",
        "from elc.user_config.types import PlannerConstraintScope",
        "from elc.user_config.controller import UserConfigController",
        "from elc.user_config.store import SqliteUserConfigStore",
        "from elc.user_config import PlannerConstraint",
        "from elc.user_config import UserConfigController",
    ):
        proc = subprocess.run(
            [sys.executable, "-c", statement],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert proc.returncode == 0, f"{statement}: {proc.stderr}"
