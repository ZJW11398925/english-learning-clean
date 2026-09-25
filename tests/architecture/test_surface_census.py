"""现役面普查（prep-0）—— 14 个顶层包的真实现面在哪，以及哪些类是有制度依据的空骨架。

本文件回答外评指出的那类问题（“interface archaeology”：新读者无法判断哪个类是
production、哪个只是契约骨架）。它不是逐类贴标签（`src/elc` 共 **520** 个公开类 /
130 文件 —— 逐类贴标签是不可维护的漂移面），而是**以包为行**的一跳索引：每行给出
该包的现役面（读者应当用的类/模块）、它自己的 durable store（若有），以及本包内
**非现役**的骨架类。

**四类词（legend）**

- ``PRODUCTION FACE``：读者应当使用的现役入口（可能是 store，也可能是 controller 或
  runtime 面）；本表的 ``live_face`` / ``store`` 两列。
- ``DURABLE STORE``：承载该包 durable 行的 SQL 实装面（本仓的分层是「authority 是端口，
  SQL 在 platform/db」——所以有的 store 落在 ``elc.platform.db.*``）。
- ``PORT``：``Protocol`` 声明的接口面（``commands`` / ``queries`` 模块）。**不入表**：
  它们的声明位置就是协议模块本身，读者按包名就能找到。
- ``LEGACY_SKELETON``：``Phase 0`` 红线要求保持空骨架的类（``tests/architecture/
  test_gate_1_domain_interfaces.py`` 钉住「每个 public 方法必须 raise
  ``NotImplementedError``」）；本表 ``skeletons`` 列。

``REFERENCE``（``behavioral_baselines/``）与 ``TEST_ONLY``（``tests/``）**不入表**：
这两类的声明位置分别在基线与测试目录，放进 src 的普查表反而会把「哪里是真的」搅混。

**能力边界（不得越读）**：本表保证的是**包级一跳可达 + 骨架/非现役可核**——即
(1) 每个顶层包恰一行；(2) 表里的符号真的 import 得到、骨架真的属于本行包；
(3) **AST 派生**的骨架集合 ⊆ 声明的骨架集合（新骨架会被抓住）；
(4) 声明的现役面**不是**骨架；(5) 骨架的两种形状（``ALL_RAISE`` / ``KEPT``）双向可核。
它**不**保证：每个类的语义分类、端口与实现的一一对应、或「表与所有代码一致」——那
后半属于 review 与 canonical 原文。也不保证散文的真值（见下一条登记）。

**登记（本表的已知限度）**

  R1 ``elc.persona`` **没有 durable store**：``CharacterPackageRecord`` 在 registry 里只
     声明了对象形状（``OWNER_PERSONA``），没有任何表或 store 写它 —— 运行时由宿主注入
     （``ConversationCoordinator`` 的 ``character_package`` 参数）。所以该行
     ``store=None`` 是诚实的事实，不是遗漏。
  R2 ``elc.world_lore`` **没有实装面**：只有两个 Protocol、``types`` 与骨架控制器；
     本行 ``no_live_face_because`` 就是这条，且带 Revisit。
  R3 ``elc.runtime`` 没有单一 store：它通过端口组合 generation / delivery / projection /
     decision-cycle 等多张表 ⇒ ``store=None``；具体 store 在各自端口模块的 docstring。
  R4 骨架计数 = **6**（5 个 ``ALL_RAISE`` + ``RuntimeOrchestrator`` 的 ``KEPT``）。
  R5 本表**不**重复 Phase 0 红线的逐-controller 检查（那由
     ``test_gate_1_domain_interfaces.py`` 承担，且其允许名单是测试内局部表、
     不可 import）；本表与它的关系是：**派生骨架集 ⊆ 本表声明的骨架集**（新骨架在
     本表亮红）。
  R6 逐类分类（520 个公开类）**不做**，理由见模块首段。
  R7 本文件由 **prep-0**（``DEC-OPI-8f27d1de-…25``）**显式授权**新增：它破了一次
     「``tests/architecture/`` 冻结面零改动」的字面 —— 只**新增**此一件，**不改**该目录
     任何既有文件。散文真值不归本表管：它只保证上述五条。
"""

from __future__ import annotations

import ast
import importlib
from dataclasses import dataclass, field

from tests.conftest import SRC_ROOT


@dataclass(frozen=True)
class Skeleton:
    """One non-live class inside a package's row.

    ``shape`` is the declaration of *how* it is a skeleton; both shapes are
    checked in both directions (a claim that does not hold turns red):

    - ``ALL_RAISE``: every public method's body only raises
      ``NotImplementedError`` (the derived shape);
    - ``KEPT``: some public methods do real work and are listed in
      ``non_raising_methods`` — every other public method must only raise,
      and every listed method must *not* only raise.
    """

    name: str
    shape: str
    non_raising_methods: tuple[str, ...] = ()
    points_to: str | None = None


@dataclass(frozen=True)
class Row:
    """One package's census row."""

    package: str
    live_face: str | None = None
    no_live_face_because: str | None = None
    store: str | None = None
    skeletons: tuple[Skeleton, ...] = field(default=())


SURFACE: tuple[Row, ...] = (
    Row(
        "content",
        live_face="elc.content.store:ContentStore",
        store="elc.content.store:ContentStore",
        skeletons=(Skeleton("ContentController", "ALL_RAISE"),),
    ),
    Row(
        "conversation",
        live_face="elc.conversation.store:SqliteConversationStore",
        store="elc.conversation.store:SqliteConversationStore",
        skeletons=(Skeleton("ConversationController", "ALL_RAISE"),),
    ),
    Row(
        "curriculum",
        live_face="elc.curriculum.provider:ContentBackedTeachingTargetProvider",
        skeletons=(Skeleton("CurriculumController", "ALL_RAISE"),),
    ),
    Row(
        "deletion",
        live_face="elc.deletion.controller:DeletionController",
        store="elc.deletion.store:SqliteDeletionStore",
    ),
    Row(
        "learning",
        live_face="elc.learning.controller:LearningController",
        store="elc.learning.store:SqliteLearningStore",
    ),
    Row(
        "persona",
        live_face="elc.persona.runtime:PersonaRuntime",
        skeletons=(Skeleton("PersonaController", "ALL_RAISE"),),
    ),
    Row("platform", live_face="elc.platform.db"),
    Row(
        "planner",
        live_face="elc.planner.controller:PlannerService",
        store="elc.platform.db.planner_store:SqlitePlannerRecordStore",
    ),
    Row(
        "relationship",
        live_face="elc.relationship.controller:RelationshipController",
        store="elc.relationship.store:SqliteRelationshipStore",
    ),
    Row(
        "runtime",
        live_face="elc.runtime.controller:ConversationCoordinator",
        skeletons=(
            Skeleton(
                "RuntimeOrchestrator",
                "KEPT",
                non_raising_methods=("runtime_epoch", "open_startup_fence"),
                points_to="elc.runtime.controller:ConversationCoordinator",
            ),
        ),
    ),
    Row(
        "scheduler",
        live_face="elc.scheduler.controller:SchedulerController",
        store="elc.scheduler.store:SqliteSchedulerStore",
    ),
    Row(
        "teaching",
        live_face="elc.teaching.controller:TeachingController",
        store="elc.teaching.store:SqliteTeachingStore",
    ),
    Row(
        "user_config",
        live_face="elc.user_config.controller:UserConfigController",
        store="elc.user_config.store:SqliteUserConfigStore",
    ),
    Row(
        "world_lore",
        no_live_face_because=(
            "该包只有 WorldLoreCommands / WorldLoreQueries 两个 Protocol、types 与"
            "骨架控制器，没有任何实装面；Persona 消费的 WorldLoreView 由注入提供。"
            "Revisit: 实装落地时把本行改成 live_face 并把这条登记删掉"
        ),
        skeletons=(Skeleton("WorldLoreController", "ALL_RAISE"),),
    ),
)


# -- the derived baseline: which classes look like skeletons -----------------


def _class_nodes_in(package: str) -> dict[str, ast.ClassDef]:
    """Every class defined under one package, name → node (duplicates named)."""

    found: dict[str, ast.ClassDef] = {}
    for path in sorted((SRC_ROOT / package).rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                found.setdefault(node.name, node)
    return found


def _public_methods(node: ast.ClassDef) -> dict[str, ast.FunctionDef]:
    return {
        member.name: member
        for member in node.body
        if isinstance(member, ast.FunctionDef) and not member.name.startswith("_")
    }


def _statements(method: ast.FunctionDef) -> list[ast.stmt]:
    """A method's body minus its docstring (the docstring is not behaviour)."""

    body = list(method.body)
    if body and isinstance(body[0], ast.Expr):
        if isinstance(body[0].value, ast.Constant):
            body = body[1:]
    return body


def _only_raises(method: ast.FunctionDef) -> bool:
    """True when the method's whole body is ``raise NotImplementedError(...)``."""

    body = _statements(method)
    if not body:
        return False
    for statement in body:
        if not isinstance(statement, ast.Raise):
            return False
        exc = statement.exc
        if not isinstance(exc, ast.Call):
            return False
        if getattr(exc.func, "id", None) != "NotImplementedError":
            return False
    return True


def _derived_skeletons() -> dict[str, set[str]]:
    """package → the classes the AST rule calls skeletons (the baseline)."""

    derived: dict[str, set[str]] = {}
    for row in SURFACE:
        names: set[str] = set()
        for name, node in _class_nodes_in(row.package).items():
            methods = _public_methods(node)
            if methods and all(_only_raises(m) for m in methods.values()):
                names.add(name)
        derived[row.package] = names
    return derived


def _packages_on_disk() -> set[str]:
    return {
        path.name
        for path in SRC_ROOT.iterdir()
        if path.is_dir() and path.name != "__pycache__"
    }


def _import_symbol(path: str) -> object:
    """Import ``module`` or ``module:Class`` (the table's spelling)."""

    module_name, _, attr = path.partition(":")
    module = importlib.import_module(module_name)
    if not attr:
        return module
    return getattr(module, attr)


def _class_in_package(package: str, name: str) -> ast.ClassDef | None:
    return _class_nodes_in(package).get(name)


# -- pins --------------------------------------------------------------------


def test_the_table_covers_exactly_the_packages_on_disk() -> None:
    """One row per top-level package under ``src/elc``, both directions: a new
    package cannot appear without a row, and a row cannot outlive its package."""

    declared = [row.package for row in SURFACE]
    assert len(declared) == len(set(declared)), "duplicate package rows"
    assert set(declared) == _packages_on_disk()


def test_every_declared_symbol_imports_and_belongs_to_its_row() -> None:
    """Every declared face/store/points_to imports, and every skeleton class is
    really defined inside its own package (a spelling mistake cannot hide)."""

    for row in SURFACE:
        for path in (row.live_face, row.store):
            if path is not None:
                assert _import_symbol(path) is not None, (row.package, path)
        for skeleton in row.skeletons:
            assert _class_in_package(row.package, skeleton.name) is not None, (
                row.package,
                skeleton.name,
            )
            if skeleton.points_to is not None:
                assert _import_symbol(skeleton.points_to) is not None, skeleton


def test_every_derived_skeleton_is_declared() -> None:
    """The AST rule is the baseline: whatever looks like a skeleton must be in
    its row's ``skeletons``. A new skeleton — or a class that graduates into a
    skeleton — turns this red until the table moves."""

    derived = _derived_skeletons()
    for row in SURFACE:
        declared = {skeleton.name for skeleton in row.skeletons}
        assert derived[row.package] <= declared, (
            f"undeclared skeleton(s) in {row.package}:"
            f" {sorted(derived[row.package] - declared)}"
        )


def test_no_declared_live_face_is_a_skeleton() -> None:
    """The table must not point at a dead class: no declared ``live_face`` /
    ``store`` / ``points_to`` may be a declared skeleton of its package (nor one
    the AST rule derives)."""

    declared = {row.package: {s.name for s in row.skeletons} for row in SURFACE}
    derived = _derived_skeletons()
    for row in SURFACE:
        paths = [row.live_face, row.store]
        paths.extend(skeleton.points_to for skeleton in row.skeletons)
        for path in paths:
            if path is None or ":" not in path:
                continue
            module_name, _, attr = path.partition(":")
            parts = module_name.split(".")
            if not parts or parts[0] != "elc" or len(parts) < 2:
                continue
            owner = parts[1]
            assert attr not in declared.get(owner, set()), f"{path} is a skeleton"
            assert attr not in derived.get(owner, set()), (
                f"{path} looks like a skeleton"
            )


def test_every_skeleton_shape_is_true_in_both_directions() -> None:
    """``ALL_RAISE`` and ``KEPT`` are claims about the class's methods, checked
    both ways: every non-exempt public method only raises, and every exempt one
    does not."""

    for row in SURFACE:
        for skeleton in row.skeletons:
            node = _class_in_package(row.package, skeleton.name)
            assert node is not None, skeleton.name
            methods = _public_methods(node)
            assert methods, f"{skeleton.name} has no public methods"
            if skeleton.shape == "ALL_RAISE":
                assert not skeleton.non_raising_methods, skeleton.name
                for name, method in methods.items():
                    assert _only_raises(method), (
                        f"{row.package}.{skeleton.name}.{name} implements logic —"
                        " the table calls it ALL_RAISE"
                    )
            elif skeleton.shape == "KEPT":
                exempt = set(skeleton.non_raising_methods)
                assert exempt, f"{skeleton.name}: KEPT needs its exemptions"
                for name, method in methods.items():
                    if name in exempt:
                        assert not _only_raises(method), (
                            f"{skeleton.name}.{name} is listed as doing work but"
                            " only raises"
                        )
                    else:
                        assert _only_raises(method), (
                            f"{row.package}.{skeleton.name}.{name} implements logic"
                            " without being declared"
                        )
            else:
                raise AssertionError(f"unknown shape {skeleton.shape!r}")


def test_each_row_declares_exactly_one_of_live_face_or_reason() -> None:
    """A row either names the live face or says why there is none — never both,
    never neither (an empty cell is how a claim silently disappears)."""

    for row in SURFACE:
        declared = [row.live_face is not None, row.no_live_face_because is not None]
        assert sum(declared) == 1, row.package
        if row.no_live_face_because is not None:
            assert "Revisit" in row.no_live_face_because, row.package


def test_the_legend_and_its_registrations_are_in_this_modules_own_words() -> None:
    """Registration-style pin over this file's text (the phase-10 precedent):
    the four legend words, the two excluded classes, the capability boundary and
    the registrations R1–R7 are here, so a later cut that wants to move them has
    to edit this module's own text.

    Capability boundary: this is a phrase-existence pin — it does not prove the
    prose is right, only that it cannot vanish silently.
    """

    flat = " ".join(__doc__.split() if __doc__ else [])
    for word in (
        "PRODUCTION FACE",
        "DURABLE STORE",
        "PORT",
        "LEGACY_SKELETON",
        "REFERENCE",
        "TEST_ONLY",
    ):
        assert word in flat, word
    for marker in ("R1", "R2", "R3", "R4", "R5", "R6", "R7"):
        assert marker in flat, marker
    assert "能力边界" in flat
    assert "不" in flat and "语义分类" in flat
    assert "prep-0" in flat and "DEC-OPI-8f27d1de-…25" in flat
