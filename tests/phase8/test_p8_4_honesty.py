"""P8-4 ⑦ — honesty: what the new modules are, and what this cut does not claim.

Three claims, all checkable:

- **the two new modules are SQL-free and import cold** (import sets declared
  and asserted by equality, no ``sqlite3`` / ``elc.platform.db`` face, no
  ``execute``-family call, and a subprocess that imports each module without
  touching a database);
- **the coordinator is still the only place that knows both sides**: it
  carries no SQL statement at all, and nothing in ``src/`` constructs the
  wiring — the automatic leg is an opt-in a caller passes, not a default;
- **nothing was widened where the decisions forbade it**: §13's reading moved
  without moving ``SHADOW_MODE_MODEL_VERSION``, ``assemble_feature_authority``'s
  signature is untouched, and the automatic unit's pre-P8-4 callers keep their
  defaults (``user_intent_scope="OPEN"``, an optional moment template, and the
  replay's ``action_id=None``).

The **rollout** claim is here too, as a constant fact rather than a promise:
the shipped corpus reports no content level for its own target, so no target
reaches BF-02 §10's automatic thresholds and this cut opens no switch — the
behavioural half (a real-corpus run answers ``NO_TARGET``) lives in
tests/phase8/test_p8_4_turn_integration.py.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import os
import subprocess
import sys
from pathlib import Path

import pytest

from elc.curriculum.store import CurriculumContentStore
from elc.planner.feature_assembly import assemble_feature_authority
from elc.planner.shadow import SHADOW_MODE_MODEL_VERSION
from elc.runtime import automatic_turn, exposure
from elc.runtime.automatic_teaching import (
    AutomaticTeachingTurn,
    TeachingControlFacts,
    decide_automatic_teaching,
)
from elc.runtime.automatic_turn import AutomaticTurnWiring
from tests.conftest import REPO_ROOT, SRC_ROOT
from tests.phase8.p8_4_world import build_content

MIGRATION_0017 = REPO_ROOT / "migrations" / "0017_ledger_event_provenance.sql"
AUTOMATIC_TURN_MODULE = SRC_ROOT / "runtime" / "automatic_turn.py"
EXPOSURE_MODULE = SRC_ROOT / "runtime" / "exposure.py"
CONTROLLER_MODULE = SRC_ROOT / "runtime" / "controller.py"
NEW_FILES = (MIGRATION_0017, AUTOMATIC_TURN_MODULE, EXPOSURE_MODULE)

#: ``elc.runtime.exposure``'s whole import set — declared, and asserted by
#: equality: the module reads the pure core and the platform's types, and
#: nothing else.
EXPOSURE_IMPORTS = {
    "__future__",
    "elc.planner.ledger",
    "elc.platform.types",
    "typing",
}

#: ``elc.runtime.automatic_turn``'s import set. It names the planner's faces,
#: the runtime unit, the exposure port and (since P8-5) the rollout stage's
#: face; it names no store, no controller and no SQL module — the wiring's
#: objects arrive as values.
AUTOMATIC_TURN_IMPORTS = {
    "__future__",
    "dataclasses",
    "elc.planner.candidates",
    "elc.planner.kernel",
    "elc.planner.ledger",
    "elc.planner.records",
    "elc.planner.scope",
    "elc.planner.shadow",
    "elc.planner.supply",
    "elc.planner.types",
    "elc.platform.types",
    "elc.runtime.automatic_teaching",
    "elc.runtime.decision_cycles",
    "elc.runtime.exposure",
    "elc.teaching.rollout",
    "elc.teaching.types",
    "elc.user_config.types",
    "typing",
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


# -- ① SQL-free, and cold imports -------------------------------------------


@pytest.mark.parametrize("path", (EXPOSURE_MODULE, AUTOMATIC_TURN_MODULE))
def test_the_new_modules_import_no_sql_face(path: Path) -> None:
    imported = _imports(path)
    assert "sqlite3" not in imported
    assert not [name for name in imported if name.startswith("elc.platform.db")]
    assert not [name for name in imported if name.startswith("elc.runtime.controller")]


@pytest.mark.parametrize("path", (EXPOSURE_MODULE, AUTOMATIC_TURN_MODULE))
def test_the_new_modules_call_no_sql_method(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in {
                "execute",
                "executemany",
                "executescript",
                "commit",
                "rollback",
            }, node.func.attr


def test_the_exposure_import_set_is_the_declared_one() -> None:
    assert _imports(EXPOSURE_MODULE) == EXPOSURE_IMPORTS


def test_the_automatic_turn_import_set_is_the_declared_one() -> None:
    assert _imports(AUTOMATIC_TURN_MODULE) == AUTOMATIC_TURN_IMPORTS


def test_the_two_modules_import_cold() -> None:
    """A cold interpreter can import both modules and use them; the one thing
    that must **not** arrive with them is the coordinator (the import graph
    that carries the package's store closure is older than this cut — the AGENTS
    note — so the claim pinned here is the direct face plus this one, and the
    static import-set pins above carry the rest)."""

    program = "\n".join(
        [
            "import os, sys",
            "ROOT = os.environ['ROOT']",
            "sys.path[:0] = [os.path.join(ROOT, 'src'), ROOT]",
            "import elc.runtime.exposure as exposure",
            "import elc.runtime.automatic_turn as automatic_turn",
            "assert exposure.ledger_event_of('OPENING') is not None",
            "assert automatic_turn.AUTOMATIC_OPEN_SLOT == 'automatic-open'",
            "assert automatic_turn.conversation_priority_view_of('NONE')",
            "assert 'elc.runtime.controller' not in sys.modules",
            "print('COLD-P8-4')",
        ]
    )
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", ROOT=str(REPO_ROOT))
    proc = subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, proc.stderr
    assert "COLD-P8-4" in proc.stdout


def test_the_wired_modules_expose_the_faces_the_controller_uses() -> None:
    assert callable(exposure.record_exposure)
    assert callable(exposure.record_skip)
    assert callable(automatic_turn.assemble_automatic_turn)
    assert callable(automatic_turn.decide_automatic_turn)
    assert callable(automatic_turn.record_leg_failure)


# -- ② the coordinator, and the opt-in --------------------------------------


def test_the_coordinator_carries_no_sql_statement() -> None:
    from tests.phase3.sql_write_scan import write_statements

    assert write_statements(CONTROLLER_MODULE) == {}
    assert "sqlite3" not in _imports(CONTROLLER_MODULE)


def _wiring_names(tree: ast.Module) -> set[str]:
    """Every module-level name that denotes ``AutomaticTurnWiring`` (the F5
    review's alias-aware step, kept and widened by the p8-5 disposal: a local
    constructor reached through an alias is still a construction, whichever
    spelling produced the alias).

    Three alias forms resolve, all module-level: an ``assign`` whose value is
    the bare name already in the set, an ``assign`` whose value is an
    *attribute* of that name (``module.AutomaticTurnWiring``), and an
    ``ImportFrom`` that renames the class (``from … import
    AutomaticTurnWiring as _Alias``). What remains beyond a name-based scan is
    registered on the test below."""

    names = {"AutomaticTurnWiring"}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            names.update(
                alias.asname or alias.name
                for alias in node.names
                if alias.name == "AutomaticTurnWiring"
            )
            continue
        value: ast.expr | None = None
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            value = node.value
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            value = node.value
            targets = [node.target]
        if isinstance(value, ast.Name):
            bound = value.id in names
        elif isinstance(value, ast.Attribute):
            bound = value.attr in names
        else:
            bound = False
        if bound:
            for target in targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
    return names


def test_nothing_in_src_constructs_the_wiring() -> None:
    """The opt-in is the caller's: no shipped module builds an
    ``AutomaticTurnWiring`` (the controller only *takes* one), so a production
    assembly that never passes it keeps the pre-P8-4 behaviour by construction.

    Review F5's registered limit is discharged here: the pin is the **AST
    form** (it walks every ``Call`` and resolves the callee name against the
    module-level aliases of the class), and its trigger — "the first cut that
    edits ``automatic_turn.py``'s wiring declaration for another reason" —
    fired in P8-5, which added the ``rollout_stage`` field. The p8-5 disposal
    (LOW-1) widened the alias resolution from bare-name assignments to the
    three module-level forms ``_wiring_names`` documents, after the review's
    M13/M14 mutations showed the two alias spellings
    (``from … import AutomaticTurnWiring as _Alias`` and
    ``_Alias = module.AutomaticTurnWiring``) were 0-RED.

    Registered limits, all kept rather than dropped: a ``**kwargs`` splat that
    reaches the constructor under another spelling, a name produced at runtime
    (``getattr`` / ``globals()``), and an alias built *inside* a function body
    are still beyond a name-based scan over the module body."""

    callers = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        if path.name == "automatic_turn.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = _wiring_names(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                called = (
                    func.id
                    if isinstance(func, ast.Name)
                    else func.attr
                    if isinstance(func, ast.Attribute)
                    else None
                )
                if called in names:
                    callers.append(path.relative_to(SRC_ROOT).as_posix())
                    break
    assert callers == []


def test_the_wiring_bundle_requires_only_the_two_faces_the_unit_needs() -> None:
    fields = {
        field.name: field.default
        for field in dataclasses.fields(AutomaticTurnWiring)
    }
    assert fields["planner_store"] is dataclasses.MISSING
    assert fields["teaching"] is dataclasses.MISSING
    for optional in (
        "learning",
        "scheduler",
        "user_config",
        "curriculum",
        "supply",
        "ledger",
        "session_budget",
        "user_id",
        "candidate_supply",
        # P8-5: the one optional field that is not a face — the process-level
        # rollout declaration. Its default is the fail-closed one (no stage),
        # and tests/phase8/test_p8_5_rollout_gate.py pins what that means.
        "rollout_stage",
    ):
        assert fields[optional] is None, optional


def test_the_supply_seam_is_the_assemblys_own_parameter() -> None:
    """``candidate_supply`` is the same injection point
    ``assemble_automatic_turn`` declares: the coordinator forwards the wiring's
    value, and ``None`` means the generators run over the ports.

    Registered limit, same family as the pin above (review F5): the forwarding
    is pinned as a normalized substring, so a rewrite that forwards the value
    through an alias or a ``**kwargs`` splat would evade the scan while keeping
    the behaviour — the review's alias-aware AST scan confirmed the fact today.
    Upgrade to the AST form with the same trigger: the first cut that touches
    the assembly's forwarding line.
    """

    source = CONTROLLER_MODULE.read_text(encoding="utf-8")
    normalized = " ".join(source.split())
    assert "supply=self._automatic.candidate_supply" in normalized
    parameter = inspect.signature(
        automatic_turn.assemble_automatic_turn
    ).parameters["supply"]
    assert parameter.default is None


def test_the_new_files_are_lf() -> None:
    """The channel discipline, made checkable: this cut's three new files were
    normalized to LF before delivery (the tracked files they sit beside keep
    their own existing blob line endings)."""

    for path in NEW_FILES:
        raw = path.read_bytes()
        assert b"\r" not in raw, path
        assert raw.endswith(b"\n"), path


# -- ③ nothing widened -------------------------------------------------------


def test_the_shadow_stamp_did_not_move() -> None:
    assert SHADOW_MODE_MODEL_VERSION == "sh2"


def test_assemble_feature_authority_signature_is_untouched() -> None:
    parameters = list(
        inspect.signature(assemble_feature_authority).parameters
    )
    assert parameters == [
        "learning_snapshot",
        "current_learning_watermark",
        "schedule_view",
        "teaching_policy",
        "goal_portfolio",
        "curriculum_readiness",
        "constraint_view_present",
        "natural_break_available",
    ]
    hints = inspect.get_annotations(
        assemble_feature_authority, eval_str=True
    )
    assert hints["natural_break_available"] is bool


def test_the_unit_keeps_its_pre_p8_4_defaults() -> None:
    signature = inspect.signature(decide_automatic_teaching)
    assert signature.parameters["user_intent_scope"].default == "OPEN"
    moment = inspect.signature(AutomaticTeachingTurn).parameters["moment"]
    assert moment.default is inspect.Parameter.empty  # still required …
    hints = inspect.get_annotations(AutomaticTeachingTurn, eval_str=True)
    assert "None" in str(hints["moment"])  # … but its type admits None


def test_the_replay_still_reports_no_action_id() -> None:
    """The unit's declared surface is unchanged (P8-1's reading): on a replay
    it reports ``action_id=None`` and the caller reads the durable action."""

    tree = ast.parse(
        (SRC_ROOT / "runtime" / "automatic_teaching.py").read_text(
            encoding="utf-8"
        )
    )
    replay = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_durable_gate_replay"
    )
    body = ast.unparse(replay)
    assert "action_id=None" in body


def test_the_controls_record_still_allows_a_hand_declared_value() -> None:
    """``TeachingControlFacts.derived`` is the wiring's face; a caller may
    still declare the record by hand (the P8-1 contract is unchanged)."""

    declared = TeachingControlFacts(automatic_teaching_enabled=True)
    assert declared.automatic_teaching_enabled is True
    assert "derived" in dir(TeachingControlFacts)


def test_the_corpus_still_cannot_answer_a_usable_level(tmp_path: Path) -> None:
    """BF-02 §10's thresholds need a level; the shipped corpus reports none —
    which is the **rollout HOLD** (no automatic/open target is reachable), and
    it is a read of the real artifact, not a promise."""

    from elc.content.store import ContentStore

    content = build_content(tmp_path / "content.db")
    real = CurriculumContentStore(ContentStore(content))
    assessment = real.readiness("res-hedge-i-think")
    assert assessment.__class__.__name__ == "Ok", assessment
    assert assessment.value.level is None
    assert assessment.value.next_level == "R0_INDEXED"
