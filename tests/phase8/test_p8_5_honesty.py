"""P8-5 ⑥ — honesty: what the new module is, and what this cut does not claim.

Four claims, all checkable:

- **the vocabularies are the documents'**: §12's rollout order and its six
  observation lines are parsed out of ``docs/IMPLEMENTATION_PLAN.md`` and
  compared with the module's constants, and BF-02 §10's four floors are parsed
  out of the frozen baseline's **first** fenced block and compared with
  :data:`GATE_ROWS` — the module re-spells none of them;
- **the module is read-only and SQL-free**: its import set is declared and
  asserted by equality, it carries no write statement, no SQL method call and
  no calibration literal, and a cold interpreter can import it — adding no SQL
  module of its own (the SQL closure its declared dependencies carry predates
  this cut; the cold test says which and why);
- **the HOLD is the honest answer**: the checker's own output over the shipped
  corpus denies any "the stage is open" claim, the module exposes no
  mutating or opening API at all, and no shipped module declares a stage of its
  own;
- **the registrations moved with the fact**: ``elc/teaching/gate.py``'s
  authority-1 registration no longer waits for p8-5, the rollout stage is
  named where the automatic leg composes it, and the two budget constants this
  cut declined to calibrate keep their P8-2 values and their single home (with
  the port's four missing whole-table faces pinned as missing, too).
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path
from typing import get_type_hints

from elc.learning.store import SqliteLearningStore
from elc.planner.ledger_store import SqliteLedgerStore
from elc.platform.db.planner_store import SqlitePlannerRecordStore
from elc.runtime import automatic_turn
from elc.teaching import rollout
from elc.teaching.rollout import (
    BACKOFF_MEANS,
    GATE_ROWS,
    OBSERVATION_INDICATORS,
    READINESS_RANK,
    ROLLOUT_STAGES,
    RUNTIME_GENERATED_READY_RULE,
    RolloutStage,
)
from elc.teaching.store import SqliteTeachingStore
from tests.conftest import REPO_ROOT, SRC_ROOT
from tests.phase3.sql_write_scan import write_statements, write_targets

ROLLOUT_MODULE = SRC_ROOT / "teaching" / "rollout.py"
GATE_MODULE = SRC_ROOT / "teaching" / "gate.py"
AUTOMATIC_TEACHING_MODULE = SRC_ROOT / "runtime" / "automatic_teaching.py"
TEACHING_INIT = SRC_ROOT / "teaching" / "__init__.py"
BUDGET_MODULE = SRC_ROOT / "teaching" / "budget.py"
IMPLEMENTATION_PLAN = REPO_ROOT / "docs" / "IMPLEMENTATION_PLAN.md"
BF02 = (
    REPO_ROOT
    / "behavioral_baselines"
    / "planner"
    / "BF-02_Planner_Decision_Spec_v1.1.md"
)

#: ``elc.teaching.rollout``'s whole import set — declared, and asserted by
#: equality: the canonical vocabulary modules, the two pure planner modules
#: (the frequency→switch table and the ledger core), the platform's types and
#: the teaching types. No store, no sqlite3, no SQL module.
ROLLOUT_IMPORTS = {
    "__future__",
    "dataclasses",
    "elc.curriculum.readiness",
    "elc.planner.feature_assembly",
    "elc.planner.ledger",
    "elc.platform.types",
    "elc.teaching.types",
    "elc.user_config.types",
    "enum",
    "typing",
}

#: The declared dependencies that are this package's own models — imported
#: first in the cold program, so the SQL closure they carry is the probe's
#: **baseline** rather than this module's addition (the cold test below).
ROLLOUT_PACKAGE_DEPENDENCIES = tuple(
    sorted(name for name in ROLLOUT_IMPORTS if name.startswith("elc."))
)

#: The two budget windows' declarations, verbatim: the text P8-5 declined to
#: move (``elc.teaching.budget``'s Revisit named p8-5 as a possible calibrator,
#: and this cut registers the decline there).
BUDGET_DECLARATIONS = {
    "COOLDOWN_WINDOW_SECONDS": "COOLDOWN_WINDOW_SECONDS: float = 1800.0",
    "RECENT_TEACHING_WINDOW_SECONDS": (
        "RECENT_TEACHING_WINDOW_SECONDS: float = 3600.0"
    ),
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


def _fenced_bodies(text: str) -> list[tuple[str, ...]]:
    """Every fenced block's non-blank body lines in ``text``, in order."""

    blocks: list[tuple[str, ...]] = []
    body: list[str] = []
    inside = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            if inside and body:
                blocks.append(tuple(body))
            body = []
            inside = not inside
            continue
        if inside and line.strip():
            body.append(line.strip())
    return blocks


def _fenced_blocks(text: str, heading: str) -> list[tuple[str, ...]]:
    """Every fenced block after ``heading``, until the next same-level heading
    (bold **not** stripped: these documents' blocks are bare)."""

    lines = text.splitlines()
    level = len(heading) - len(heading.lstrip("#"))
    start = next(
        index for index, line in enumerate(lines) if line.strip() == heading
    )
    end = start + 1
    while end < len(lines):
        stripped = lines[end].strip()
        if stripped.startswith("#"):
            head_level = len(stripped) - len(stripped.lstrip("#"))
            if head_level <= level:
                break
        end += 1
    return _fenced_bodies("\n".join(lines[start:end]))


def _ip12_blocks() -> list[tuple[str, ...]]:
    return _fenced_blocks(
        IMPLEMENTATION_PLAN.read_text(encoding="utf-8"),
        "## 12. Detail Block — Automatic Teaching Rollout"
        "（Post-BF Phase 8 late stage）",
    )


def _bf02_section(text: str, heading: str) -> str:
    lines = text.splitlines()
    start = next(
        index for index, line in enumerate(lines) if line.strip() == heading
    )
    end = start + 1
    while end < len(lines):
        stripped = lines[end].strip()
        if stripped.startswith("## "):
            break
        end += 1
    return "\n".join(lines[start:end])


# -- ① the vocabularies are the documents' -----------------------------------


def test_the_four_stage_words_are_section_12s_block() -> None:
    blocks = _ip12_blocks()
    order = [
        line.lstrip("→ ").strip() for line in blocks[0]
    ]
    assert order == [
        "manual/user-initiated",
        "Study-first",
        "Balanced",
        "Lounge",
    ]
    assert [stage.value for stage in ROLLOUT_STAGES] == order


def test_the_six_indicators_are_section_12s_block() -> None:
    blocks = _ip12_blocks()
    observed = tuple(blocks[1])
    assert observed == (
        "unwanted interruption",
        "skip/reject",
        "continuation",
        "NO_TARGET appropriateness",
        "overexposure",
        "Evidence gain",
    )
    assert OBSERVATION_INDICATORS == observed


def test_the_backoff_rule_is_section_12s_own() -> None:
    blocks = _ip12_blocks()
    assert blocks[2] == ("提高 threshold / policy cost",)
    plan = IMPLEMENTATION_PLAN.read_text(encoding="utf-8")
    assert "而不是修改 Learning truth" in plan
    text = " ".join(BACKOFF_MEANS)
    assert "threshold" in text
    assert "policy cost" in text
    assert "Learning truth" in text
    # The one thing that may never be the lever.
    assert "never by changing Learning truth" in text


def test_the_four_floors_are_bf_02_section_10s_block() -> None:
    """§10's *first* fenced block is the four floors, and it is read **as the
    block**.

    The p8-5 disposal's F1: the as-found form scanned every line of the section
    for a last word starting with ``R`` and took ``tail[1]`` as the rank — so
    it also read §10's second sentence (whose fenced ``user-initiated`` and
    ``automatic CURRENT_USER_ERROR R1/R2/R3`` blocks and whose closing prose
    line ending ``…绕过 R3。`` all match) as two further floors, and its rank
    digit only happened to be right for ``R2+``/``R4``. The block's own row
    shape is ``<row word>  R<n>[+]``, parsed here as such."""

    section = _bf02_section(
        BF02.read_text(encoding="utf-8"),
        "## 10. Readiness 与 runtime-generated content",
    )
    blocks = _fenced_bodies(section)
    assert blocks, section
    rows: list[tuple[str, int]] = []
    for line in blocks[0]:
        head, _, tail = line.rpartition(" ")
        assert tail[:1] == "R", line
        rows.append((head.strip(), int(tail[1:].rstrip("+"))))
    assert rows == [
        ("PROBE", 2),
        ("user-initiated teaching", 3),
        ("automatic general/review", 3),
        ("automatic CURRENT_USER_ERROR", 4),
    ]
    assert [
        (spec.row_word, READINESS_RANK[spec.required_level]) for spec in GATE_ROWS
    ] == rows


def test_the_runtime_generated_ready_rule_is_bf_02s_own() -> None:
    section = _bf02_section(
        BF02.read_text(encoding="utf-8"),
        "## 10. Readiness 与 runtime-generated content",
    )
    assert "runtime_generated_ready" in section
    assert "R4" in section and "R3" in section
    assert "runtime_generated_ready" in RUNTIME_GENERATED_READY_RULE
    assert "R4" in RUNTIME_GENERATED_READY_RULE
    assert "R3" in RUNTIME_GENERATED_READY_RULE


def test_no_function_reads_the_fallback_flag() -> None:
    """§10's second sentence is a *rule about the checker*, not a value the
    checker takes: the identifier appears in the module only as the declared
    string, never as a parameter, argument or attribute."""

    tree = ast.parse(ROLLOUT_MODULE.read_text(encoding="utf-8"))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.arg):
            names.append(node.arg)
        elif isinstance(node, ast.Name):
            names.append(node.id)
        elif isinstance(node, ast.Attribute):
            names.append(node.attr)
    assert "runtime_generated_ready" not in names


# -- ② read-only and SQL-free ------------------------------------------------


def test_the_rollout_import_set_is_the_declared_one() -> None:
    assert _imports(ROLLOUT_MODULE) == ROLLOUT_IMPORTS


def test_the_module_names_no_sql_face() -> None:
    imported = _imports(ROLLOUT_MODULE)
    assert "sqlite3" not in imported
    assert not [name for name in imported if name.startswith("elc.platform.db")]
    assert "elc.runtime.controller" not in imported


def test_the_module_carries_no_write_statement() -> None:
    assert write_statements(ROLLOUT_MODULE) == {}
    assert write_targets(ROLLOUT_MODULE) == set()


def test_the_module_calls_no_sql_method() -> None:
    tree = ast.parse(ROLLOUT_MODULE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in {
                "execute",
                "executemany",
                "executescript",
                "commit",
                "rollback",
            }, node.func.attr


def test_the_module_carries_no_calibration_literal() -> None:
    """This cut declined the budget constants' p8-5 calibration clause: no
    numeric literal that could be one of those windows appears here."""

    tree = ast.parse(ROLLOUT_MODULE.read_text(encoding="utf-8"))
    literals = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float))
    }
    assert not literals.intersection({1800, 3600, 1800.0, 3600.0})


def test_the_budget_constants_are_untouched() -> None:
    """This cut declined the budget windows' p8-5 calibration clause (module
    docstring ⑥), and "declined" is checkable three ways: the values are still
    P8-2's, each constant is declared **once** — in ``budget.py``, nowhere else
    in ``src/`` — and neither module imports the other.

    The p8-5 disposal's F2: the as-found form stripped the declaration text
    out of ``budget.py`` and asserted the *name* appears nowhere else in it —
    but that module's own P8-2 docstring references both constants (``:data:``
    roles, the window prose, and the arithmetic that uses them), so the
    assertion was false for reasons this cut has nothing to do with, and it
    pinned no property of this cut at all.

    Registered limit (p8-5 disposal, INFO-5): the "one home" probe below keys
    on ``f"{name}:"`` — the *annotated* declaration spelling — so a second,
    unannotated ``NAME = …`` declaration elsewhere in ``src/`` would not enter
    its net. The tightening trigger is the first real calibration of either
    constant (a cut that has to prove the single-home property buys the
    AST-level probe)."""

    from elc.teaching.budget import (
        COOLDOWN_WINDOW_SECONDS,
        RECENT_TEACHING_WINDOW_SECONDS,
    )

    assert COOLDOWN_WINDOW_SECONDS == 1800.0
    assert RECENT_TEACHING_WINDOW_SECONDS == 3600.0
    assert "elc.teaching.budget" not in _imports(ROLLOUT_MODULE)
    budget_source = BUDGET_MODULE.read_text(encoding="utf-8")
    assert not [
        name
        for name in _imports(BUDGET_MODULE)
        if name.startswith("elc.teaching.rollout")
    ]
    for name, declaration in BUDGET_DECLARATIONS.items():
        assert budget_source.count(declaration) == 1, name
        homes = [
            path.relative_to(SRC_ROOT).as_posix()
            for path in sorted(SRC_ROOT.rglob("*.py"))
            if f"{name}:" in path.read_text(encoding="utf-8")
        ]
        assert homes == ["teaching/budget.py"], (name, homes)


def test_the_module_imports_cold_and_adds_no_sql_module() -> None:
    """A cold interpreter imports the module and uses the stage face — and that
    import **adds no SQL module of its own**.

    ``sqlite3`` / ``elc.platform.db`` are in the closure of the module's own
    declared dependencies *before* it is imported: ``elc.teaching``'s package
    ``__init__`` re-exports the controller → store chain (a P3-1B shape P8-1's
    honesty test registers for ``elc.teaching.gate``). The p8-5 disposal's F3:
    the as-found form asserted ``'elc.platform.db' not in sys.modules`` after
    the import, which no module of this package can satisfy — it measured the
    package's pre-existing closure, not this cut's (the P8-0/P8-1 precedent:
    the *direct* import face is what a new module owns, the transitive one is
    the package's). The premise itself is asserted first, so if the closure
    ever changes this test says so instead of passing vacuously."""

    program = "\n".join(
        [
            "import os, sys",
            "ROOT = os.environ['ROOT']",
            "sys.path[:0] = [os.path.join(ROOT, 'src'), ROOT]",
            *(f"import {name}" for name in ROLLOUT_PACKAGE_DEPENDENCIES),
            # The premise of the narrowed claim, machine-checked: the declared
            # dependencies already carry the SQL closure, so what the diff
            # below measures can only be this module's own addition.
            "assert 'elc.platform.db' in sys.modules",
            "before = set(sys.modules)",
            "import elc.teaching.rollout as rollout",
            "added = sorted(set(sys.modules) - before)",
            "assert added == ['elc.teaching.rollout'], added",
            "offenders = [n for n in added if n == 'sqlite3'"
            " or n.startswith('elc.platform.db')]",
            "assert not offenders, offenders",
            "assert rollout.RolloutStage.STUDY_FIRST.value == 'Study-first'",
            "assert rollout.stage_allows_automatic(None) is False",
            "assert 'elc.runtime.controller' not in sys.modules",
            "print('COLD-P8-5')",
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
    assert "COLD-P8-5" in proc.stdout


def test_the_module_is_not_re_exported_by_the_package() -> None:
    """The P5-0 leaf precedent: a module with no store side stays importable by
    its full path and is not folded into the package's ``__init__``."""

    assert "rollout" not in TEACHING_INIT.read_text(encoding="utf-8")


# -- ③ the HOLD is the honest answer -----------------------------------------


def test_the_shipped_corpus_denies_any_open_claim(tmp_path: Path) -> None:
    """The pin the task book asks for, at C3-R1's truth — as a two-layer
    statement (旧真值: the checker answered HOLD on every row, so the
    capable claim failed at the content gate itself; C1: one authored target
    reached R4 and every row answered GO; C2-a: nine RESOURCE targets reached
    R4; C2-b: twenty-eight; C3-a: forty-six; C3-b: sixty-four; 新真值 C3-R1:
    the sixteen RESOURCE targets whose §24.7 row is a curriculum mapping
    reach R4 — the honest fall-back the re-review made on purpose,
    so all four rows
    read sixteen usable targets and the content gate answers **GO** — and
    the capable corpus *still* produces no opening claim): the rollout switch
    composes the stage leg with the content gate, no stage is declared anywhere
    in the shipped product, so ``automatic_teaching_enabled`` is False for
    every §5.1 frequency word. "语料 capable" and "rollout 已开闸" stay two
    different claims, and "阶段已就绪" remains a claim this repository cannot
    make."""

    from elc.content.build import build_content_db
    from elc.content.store import ContentStore
    from elc.curriculum.store import CurriculumContentStore
    from elc.platform.types import Ok
    from elc.teaching.rollout import (
        RolloutVerdict,
        automatic_teaching_enabled_of,
        corpus_rollout_gate,
        stage_allows_automatic,
    )
    from elc.user_config.types import TeachingFrequency

    path = tmp_path / "content.db"
    build_content_db(path)
    report = corpus_rollout_gate(CurriculumContentStore(ContentStore(path)))
    assert isinstance(report, Ok), report
    # Layer one: content capable — every row GO on the sixteen R4 mapping
    # targets (C3-R1's fall-back: the R2 fact reads a mapping, not a row).
    assert report.value.verdict is RolloutVerdict.GO
    assert report.value.automatic_verdict is RolloutVerdict.GO
    assert all(
        row.usable_targets == 16 and row.verdict is RolloutVerdict.GO
        for row in report.value.rows
        if row.automatic
    )
    # Layer two: no open claim — the stage leg is undeclared and refuses,
    # so the composed switch denies automatic teaching regardless of the
    # corpus's capability or the user's §5.1 frequency word.
    assert stage_allows_automatic(None) is False
    for frequency in (None, *TeachingFrequency):
        assert (
            automatic_teaching_enabled_of(
                stage=None, teaching_frequency=frequency
            )
            is False
        )


def test_the_module_exposes_no_opening_api() -> None:
    """Nothing here can open a stage: no name in the public surface carries a
    mutating or opening verb (the read face derives a bool; it never sets
    one), every exported name resolves, and the three faces a caller needs —
    the stage vocabulary, the stage order and the four floors — are exported.

    The p8-5 disposal's F4: the as-found form asserted ``"stages" in public``
    immediately above the ``"ROLLOUT_STAGES" in public`` line — a lower-case
    name no module declares, i.e. a copy-paste slip that could only ever fail
    and that pinned nothing beyond the line below it."""

    public = rollout.__all__
    assert public
    for name in public:
        assert not name.startswith(("set_", "open_", "mark_", "activate_")), name
    assert len(public) == len(set(public))
    assert all(hasattr(rollout, name) for name in public)
    assert "RolloutStage" in public
    assert "ROLLOUT_STAGES" in public
    assert "GATE_ROWS" in public


# -- ④ the registrations moved with the fact ---------------------------------


def test_the_gate_registration_no_longer_waits_for_p8_5() -> None:
    source = GATE_MODULE.read_text(encoding="utf-8")
    assert "p8-5 landed the stage face" in source
    assert "elc.teaching.rollout" in source
    assert "lands the durable read face for this fact's caller" not in source


def test_the_automatic_leg_names_the_stage_face() -> None:
    """The automatic leg's wiring carries the stage face: the field is declared
    ``RolloutStage | None`` (pinned by the annotation, not by its default —
    the default is the fail-closed ``None``, and the next test pins that).

    The p8-5 disposal's F5: the as-found form ended in ``… or
    AutomaticTurnWiring.model_fields`` — a pydantic attribute, which this
    dataclass does not have, reached precisely when the left operand is false
    (which it always is, the field's default being ``None``) ⇒ a guaranteed
    ``AttributeError``."""

    source = AUTOMATIC_TEACHING_MODULE.read_text(encoding="utf-8")
    assert "elc.teaching.rollout" in source
    assert "p8-5" in source
    assert "rollout_stage" in automatic_turn.__doc__
    hints = get_type_hints(automatic_turn.AutomaticTurnWiring)
    assert hints["rollout_stage"] == RolloutStage | None


def test_the_wiring_field_defaults_to_no_declaration() -> None:
    """The fail-closed default lives in the *dataclass* (``None``); the p8-4
    test world's helper declares ``Study-first`` explicitly, and the difference
    between the two is what this cut's tests pin."""

    import dataclasses

    fields = {
        field.name: field.default
        for field in dataclasses.fields(automatic_turn.AutomaticTurnWiring)
    }
    assert fields["rollout_stage"] is None
    from tests.phase8.p8_4_world import wiring

    assert (
        wiring.__defaults__ is None
    )  # keyword-only parameters carry no positional defaults
    import inspect

    signature = inspect.signature(wiring)
    assert (
        signature.parameters["rollout_stage"].default
        is RolloutStage.STUDY_FIRST
    )


def test_four_of_the_five_port_reads_have_no_durable_face() -> None:
    """The port's registered gap, pinned as a fact: the ledger read is real,
    the four whole-table enumerations are not implemented by any store.

    (The as-found form of this test — the p8-5 disposal's F6 — named
    ``SqliteTeachingStore`` without importing it, so it raised ``NameError``
    before asserting anything.)"""

    assert hasattr(SqliteLedgerStore, "read_ledger")
    assert not hasattr(SqliteTeachingStore, "list_moments")
    assert not hasattr(SqliteTeachingStore, "list_gate_decisions")
    assert not hasattr(SqlitePlannerRecordStore, "list_planner_decisions")
    assert not hasattr(SqliteLearningStore, "count_evidence_claims")


def test_no_shipped_module_declares_a_stage_of_its_own() -> None:
    """The stage is a **process-level declaration** (§12 is release
    configuration, module ①): the fact lives in a construction/injection
    parameter, so no migration carries it, and no shipped module outside the
    stage face itself names a concrete stage member — i.e. no source text can
    declare a stage open on the product's behalf. A production assembly that
    reads the stage from configuration would name it through this face; a
    literal in *src/* would be the thing this pin forbids."""

    for path in sorted((REPO_ROOT / "migrations").glob("*.sql")):
        assert "rollout" not in path.read_text(encoding="utf-8").lower(), path
    for path in sorted(SRC_ROOT.rglob("*.py")):
        if path.name == "rollout.py":
            continue
        assert "RolloutStage." not in path.read_text(
            encoding="utf-8"
        ), path.relative_to(SRC_ROOT).as_posix()


def test_the_new_test_world_declares_its_probe_sql() -> None:
    """The four probes the adapter adds are declared as constants, read-only,
    and confined to the test world (no src module carries them)."""

    from tests.phase8 import p8_5_world

    for statement in (
        p8_5_world.LIST_MOMENT_CONVERSATIONS,
        p8_5_world.LIST_GATE_CYCLES,
        p8_5_world.LIST_DECISION_CYCLES,
        p8_5_world.COUNT_CLAIMS,
    ):
        head = statement.strip().split(" ", 2)[0].upper()
        assert head in {"SELECT"}, statement
    for path in sorted(SRC_ROOT.rglob("*.py")):
        assert "LIST_MOMENT_CONVERSATIONS" not in path.read_text(
            encoding="utf-8"
        ), path


def test_the_rollout_module_is_the_only_new_src_file() -> None:
    """This cut adds one src module and no migration of its own: 0017 is in
    the chain and no SQL file was added for the rollout gate. The pin keeps
    the membership claim and no position claim — later migrations move the
    head (P9-1's 0018_delivery_records is one), and "this cut added no
    migration" is a fact about what 0017's file set contains."""

    migrations = sorted(
        path.name for path in (REPO_ROOT / "migrations").glob("*.sql")
    )
    assert "0017_ledger_event_provenance.sql" in migrations
    assert (SRC_ROOT / "teaching" / "rollout.py").exists()
