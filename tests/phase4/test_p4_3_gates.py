"""P4-3 ⑤ — the gates around this slice (TASK-…19 ⑤).

Three families, one file:

- **Gate item 1** (docs/IMPLEMENTATION_PLAN.md §2 "每个 Domain 有 own
  command/query interfaces"): ``UserConfigController`` graduated — the
  authorization is the ``phase1_class_allowlist`` entry, and the graduation
  is real (the P4-3 faces do not raise, and P6-0 landed the three faces that
  raised a phase pointer; the behaviour of all six lives in tests/phase4 and
  tests/phase6);
- **Gate item 5** ("Goal/Policy/Profile … 均有 owner/schema"): the registry
  still names this context as the owner of the profile and disclosure
  schemas, and the schema types are the ones this slice rewrote;
- **the package pins this slice must not break**: the relationship
  package's P4-G1 consumption surface (no learning/teaching/persona import,
  no denied symbol — with the canary) still holds *with* the two new
  modules, and the persona package still imports neither teaching nor
  learning.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

from elc.platform.registry import CANONICAL_OBJECTS
from elc.user_config import UserConfigController
from elc.user_config.types import DisclosurePolicy, UserProfile
from tests.conftest import SRC_ROOT

#: The two packages the P4-G1 gate names (BF-05
#: ``provider_actions.RELATIONSHIP_PROPOSAL`` deny list + DOMAIN_MODEL §17).
RELATIONSHIP_DENIED_PACKAGES = ("elc.learning", "elc.teaching", "elc.persona")

#: Packages the persona package may not import (the P3 D-INV-002 pin, kept
#: and extended to Learning here).
PERSONA_DENIED_PACKAGES = ("elc.teaching", "elc.learning")


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _offenders(package: str, forbidden: tuple[str, ...]) -> list[str]:
    found: list[str] = []
    for path in sorted((SRC_ROOT / package).rglob("*.py")):
        for module in _imported_modules(path):
            for denied in forbidden:
                if module == denied or module.startswith(f"{denied}."):
                    found.append(f"{path.relative_to(SRC_ROOT)}: {module}")
    return found


# -- Gate item 1: the graduated controller ----------------------------------


def test_the_controller_graduated_in_gate_item_1_allowlist() -> None:
    """The authorization is the allowlist entry itself (the P3-0/P3-1A/P4-1
    graduation mechanism) — this pin reads the source of the gate so a
    future deletion of the entry is caught where it would be made."""

    gate = (
        SRC_ROOT.parent.parent
        / "tests"
        / "architecture"
        / "test_gate_1_domain_interfaces.py"
    )
    source = gate.read_text(encoding="utf-8")
    assert '"user_config": {"UserConfigController"}' in source


def test_the_graduated_faces_do_not_raise() -> None:
    """The graduation is real: every P4-3 face returns a Result (the store
    is the only collaborator it needs)."""

    import inspect

    for name in (
        "upsert_user_profile",
        "set_disclosure_policy",
        "get_user_profile",
        "get_disclosed_user_profile",
    ):
        source = inspect.getsource(getattr(UserConfigController, name))
        assert "NotImplementedError" not in source, name


def test_the_phase_six_faces_graduated() -> None:
    """P4-3 pinned the three faces as unimplemented skeletons; P6-0
    (TASK-OPI-a68fd9eb-….48 ④) landed them, so the pin now reads the other
    way: no phase pointer survives on this controller, and each face
    delegates to the store (the behaviour is pinned in tests/phase6)."""

    import inspect

    for name in (
        "upsert_goal_portfolio",
        "upsert_teaching_policy",
        "set_session_focus",
    ):
        source = inspect.getsource(getattr(UserConfigController, name))
        assert "NotImplementedError" not in source, name
        assert "self._store" in source, name


def test_the_command_and_query_interfaces_still_exist() -> None:
    commands = importlib.import_module("elc.user_config.commands")
    queries = importlib.import_module("elc.user_config.queries")
    assert any(
        name.endswith("Commands") for name in vars(commands)
    ), "elc.user_config lacks a *Commands interface"
    assert any(
        name.endswith("Queries") for name in vars(queries)
    ), "elc.user_config lacks a *Queries interface"


# -- Gate item 5: the registry ----------------------------------------------


def test_the_registry_still_owns_the_profile_and_disclosure_schemas() -> None:
    profile = CANONICAL_OBJECTS["user_profile"]
    assert profile.owner == "user_config"
    assert profile.schema is UserProfile
    policy = CANONICAL_OBJECTS["disclosure_policy"]
    assert policy.owner == "user_config"
    assert policy.schema is DisclosurePolicy


def test_the_registry_schema_types_are_the_canonical_column_sets() -> None:
    import dataclasses

    assert tuple(f.name for f in dataclasses.fields(UserProfile)) == (
        "user_profile_id",
        "revision",
        "profile_facts",
        "preferences",
        "settings",
        "updated_at",
    )
    assert tuple(f.name for f in dataclasses.fields(DisclosurePolicy)) == (
        "disclosure_policy_id",
        "revision",
        "rules",
        "updated_at",
    )


# -- the duplicated window constant and its equality pin --------------------


def test_the_episode_window_matches_the_persona_window() -> None:
    """Review INFO-1: the window size is declared twice — once by the runtime
    (``CONVERSATION_WINDOW_MAX_TURNS``) and once by the Episode projection
    (``EPISODE_WINDOW_MAX_TURNS``) — because P4-G1 forbids
    ``elc.relationship`` importing ``elc.runtime``, so neither module may
    reference the other's constant. This test is what holds them equal: an
    episode is a projection of the same window the persona reads, and a
    silent divergence would make the episode's start/end bounds describe a
    different transcript than the prompt's history section."""

    from elc.relationship.episode import EPISODE_WINDOW_MAX_TURNS
    from elc.runtime.controller import CONVERSATION_WINDOW_MAX_TURNS

    assert EPISODE_WINDOW_MAX_TURNS == CONVERSATION_WINDOW_MAX_TURNS
    # Both directions of the cross-reference exist, so a reader of either
    # constant learns about the other and about this pin.
    episode_source = (SRC_ROOT / "relationship" / "episode.py").read_text(
        encoding="utf-8"
    )
    assert "CONVERSATION_WINDOW_MAX_TURNS" in episode_source
    assert "tests/phase4/test_p4_3_gates.py" in episode_source
    controller_source = (SRC_ROOT / "runtime" / "controller.py").read_text(
        encoding="utf-8"
    )
    assert "EPISODE_WINDOW_MAX_TURNS" in controller_source
    assert "tests/phase4/test_p4_3_gates.py" in controller_source


# -- the package pins this slice must not break -----------------------------


def test_the_relationship_package_still_respects_the_p4_g1_surface() -> None:
    """With the two P4-3 modules in place (episode.py / episode_store.py),
    the consumption surface is unchanged: no denied package is imported by
    any module of the relationship package."""

    offenders = _offenders("relationship", RELATIONSHIP_DENIED_PACKAGES)
    assert not offenders, offenders
    # The scan is not vacuous: the modules this slice added really are in it
    # (and they reach the conversation domain, which is allowed).
    modules = _imported_modules(SRC_ROOT / "relationship" / "episode.py")
    assert "elc.conversation.commands" in modules
    assert "elc.platform.types" in modules


def test_the_p4_g1_denied_symbols_are_still_absent() -> None:
    """The symbol half of the same gate (the P4-1 denial words + the three
    VAL-…72 ⑤ words), re-checked over the package the way
    tests/phase4/test_p4_g1_recorder_gate.py checks it."""

    denied = (
        "LearnerState",
        "LearningEvidence",
        "TeachingTrace",
        "OtherPersonaRelationship",
        "APISecret",
        "RawLearningEvidence",
        "RawDiagnostics",
        "DeletionLedger",
        "TeachingDirective",
        "AttemptEvaluation",
    )
    offenders: list[str] = []
    for path in sorted((SRC_ROOT / "relationship").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    names.add(alias.name.split(".")[-1])
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    names.add(alias.name)
        for symbol in sorted(names):
            if symbol in denied:
                offenders.append(f"{path.relative_to(SRC_ROOT)}: {symbol}")
    assert not offenders, offenders


def test_the_persona_package_imports_neither_teaching_nor_learning() -> None:
    """D-INV-002, unchanged by P4-3: the compiler renders the views it is
    handed and never reaches into the teaching or learning packages."""

    offenders = _offenders("persona", PERSONA_DENIED_PACKAGES)
    assert not offenders, offenders


def test_the_persona_package_reaches_the_views_by_type_only() -> None:
    """The other side of the same coin: P4-3 typed the GenerationContext
    views, so the persona package *does* import their owning modules — and
    only the type modules, never a store, a controller or a platform DB
    module."""

    modules = _imported_modules(SRC_ROOT / "persona" / "types.py")
    assert "elc.relationship.episode" in modules
    assert "elc.relationship.types" in modules
    assert "elc.user_config.types" in modules
    for module in modules:
        assert not module.startswith("elc.platform.db")
        assert not module.endswith(".store")


def test_the_cold_start_surface_of_the_new_module_is_annotation_only() -> None:
    """The cold-start rule, pinned structurally.

    ``elc.runtime.__init__`` imports ``persona_views``, and
    ``elc.conversation.commands`` imports ``elc.runtime.types`` — so a
    *runtime* import of a view module here closes the cycle
    ``conversation.commands → runtime.__init__ → persona_views →
    relationship.episode → conversation.commands`` and makes
    ``import elc.conversation`` fail depending on which package a caller
    imported first. The P4-3 probe caught exactly that; the view imports in
    this module are therefore annotation-only, behind ``if TYPE_CHECKING``
    (PEP 563 keeps the annotations as strings), and this pin keeps them
    there.

    The pin is scoped to the module this slice added on purpose: the rest of
    the runtime package either predates it (``controller`` is lazily loaded
    by the package ``__init__``, ``commands`` reaches only
    ``elc.conversation.types``, which is a leaf) or is already covered by
    the cold-interpreter test below.
    """

    path = SRC_ROOT / "runtime" / "persona_views.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    guarded: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and _is_type_checking(node.test):
            for statement in node.body:
                for inner in ast.walk(statement):
                    guarded.add(getattr(inner, "lineno", -1))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if node.lineno in guarded:
            continue
        modules = (
            [alias.name for alias in node.names]
            if isinstance(node, ast.Import)
            else [node.module or ""]
        )
        for module in modules:
            for denied in (
                "elc.conversation",
                "elc.relationship",
                "elc.user_config",
                "elc.persona",
                "elc.learning",
                "elc.teaching",
            ):
                if module == denied or module.startswith(f"{denied}."):
                    offenders.append(f"{path.name}: {module}")
    assert not offenders, offenders
    # The scan is not vacuous: the module really does import the view
    # modules — behind TYPE_CHECKING (which is why the pin above passes).
    source = path.read_text(encoding="utf-8")
    assert "if TYPE_CHECKING:" in source
    assert "from elc.relationship.episode import EpisodeView" in source


def _is_type_checking(test: ast.expr) -> bool:
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    return isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"


def test_every_package_imports_from_a_cold_interpreter() -> None:
    """The symptom itself, and the strongest form of the pin: a fresh
    interpreter importing one package first must succeed, for every package
    a caller could reasonably start from. (The subprocess run follows
    tests/behavioral/test_estimator_stress.py's pattern.)"""

    import os
    import subprocess
    import sys

    from tests.conftest import REPO_ROOT
    from tests.conftest import SRC_ROOT as SRC

    env = dict(
        os.environ,
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=str(SRC.parent),
    )
    for package in (
        "elc.conversation",
        "elc.relationship",
        "elc.user_config",
        "elc.persona",
        "elc.runtime",
        "elc.platform.registry",
        "elc.learning",
        "elc.teaching",
    ):
        proc = subprocess.run(
            [sys.executable, "-c", f"import {package}"],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert proc.returncode == 0, f"{package}: {proc.stderr}"


def test_the_runtime_package_still_carries_no_sql_surface() -> None:
    """Gate item 2, re-checked over the module this slice added
    (elc/runtime/persona_views.py): the runtime package may not import DB
    machinery, call execute/commit/rollback, or carry SQL text — the
    architecture test covers this, and this pin keeps the new module honest
    at the point where it is easiest to drift."""

    modules = _imported_modules(SRC_ROOT / "runtime" / "persona_views.py")
    assert "sqlite3" not in modules
    for module in modules:
        assert not module.startswith("elc.platform.db")
    tree = ast.parse(
        (SRC_ROOT / "runtime" / "persona_views.py").read_text(encoding="utf-8")
    )
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in {
                "execute",
                "executemany",
                "executescript",
                "commit",
                "rollback",
            }
