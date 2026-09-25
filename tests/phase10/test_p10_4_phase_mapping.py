"""P10-4 交付 E —— 相位级映射表：25 类 × IP §11 七类扫面 × RA §23 五 checkpoint
× 四项不变量。

A 半（`test_p10_1_failure_scenarios_a.py`）与 B 半
（`test_p10_2_failure_scenarios_b.py`）各自带一张汇总表；本文件把它们**升格**为一张
相位级映射表：25 类逐类映射到三个维度，且**可核**——一条测试逐行走表，每个 tag 在
它自己的源文件里唯一命中（tag 的 snake_case 是唯一一个 `test_` 函数名的前缀）、
**每文件无 tag 逃出表外**（集合相等）、源文件的权威常量（A 半 `SCENARIOS` 的
checkpoint/残件字面量、B 半 `SCENARIOS` 的残件字面量与 `INVARIANTS` 的四问短答）
**逐行对账**。

三个维度怎么读：

- **IP §11 七类扫面**：七类名**从 canonical 现读**（`docs/IMPLEMENTATION_PLAN.md` §11
  的 `Recovery worker 扫` fenced 块），不是记忆；表的 `scan_class` 必须是这七类之一，
  或 `RA_22_ONLY_CLASS`（`ServerDeliveryRecord` —— RA §22 的**第八类**，IP §11 七类
  之外，两条语句现读现证），或 `None`（该行没有单一扫面名，`scan_note` 写明为什么）。
  非 `None` 的行还要过一条交叉检查：该类的判别词（`SCAN_KEYWORDS`）必须出现在**源文件
  自带**的残件字面量里（表不重打那些字面量，现读现比）。
- **RA §23 五 checkpoint**：五个标题**从 canonical 现读**
  （`docs/RUNTIME_ARCHITECTURE.md` §23 的 `###` 标题）。A 半的行按源文件字面量落在
  这五格或落在第六格（CP4 窗口，登记
  N1）；B 半的 12 类是「进程没有崩、但某个面不工作」的失败形态，**不属** §23 的崩溃
  checkpoint ⇒ 该列是哨兵 `NOT_A_CRASH_WINDOW`（不把 B 半强行归格——那会发明语义）。
  最后一条断言：五格**每格至少一个 tag 见证**。
- **四项不变量**：每行四个**适用性类别**（`适用` / `N/A`）。A 半的行由该 tag 自己的
  `test_` 函数 docstring 现读现分类（`(i)…(iv)` 逐标记取段、`适用`/`N/A` 取头词；共享
  答案形态 `(i)(ii) 适用：…` 按下一段继承），B 半的行由 `INVARIANTS` 的四条短答取头词。

**F2 能力边界（不得越读）**：本表与这三个维度的钉子保证的是**文本一致与命名覆盖** ——
tag/维度值在两处文本间不漂移、源文件没有 tag 逃出表外、每格有人见证。它**不校验**表与
测试体的**语义真值**：一个 tag 在测试体里究竟证了什么、`适用`/`N/A` 的判断对不对，
不在本钉的证明范围内。因此本钉**不得引用为「表与测试体一致」的机器证明**；那一半属于
review 与 canonical 原文。

表末登记（`REGISTRATIONS`，§1 的七项 + 本刀新增三项；完整句在下面）：

    R1 场景 8 的 §22 行在和解后仍未 terminal_at 冻结（既有已登记分歧；本表只钉现状）
    R2 F2：本钉保证文本一致与命名覆盖，不校验表与测试体的语义真值
    R3 p10-1 的 6 类的 (i) 以弱形态钉（两次 recovery 之间的行数守恒；绝对计数形态由
       类 3/9/10 承担）
    R4 p10-3 的 ②侧世界无 pending 行（读失败臂只证「发出去 + 被记录」，
       不证「看不见的 STOP」）
    R5 p10-3 F5：RA §18 首句 "cancel current stream if possible"、RA:825 R-INV-015、
       RA:698 可用未用
    R6 p10-3 F6：「封闭列表」是读法，不是 canonical 的形容
    R7 ①/②两裁定的重开条件写在模块内（pre_delivery_guard 的 UNCHECKED 段 /
       controller 的 _delivery_interrupted 段）
    N1 13 号的 checkpoint 字面量不在 RA §23 五格内（A 半原表的第六值，逐字保留）
    N2 A 半模块级 (ii) 行与 8/9/10 逐类文本的措辞差异（模块表把它们记作「适用
       （group 绝对计数守恒）」，三类逐类 docstring 写「N/A 且已留痕」）——本表按逐类
       文本取值并登记该差异（不改 A 半文件）
    N3 ConversationCoordinatorLease 在 Local V1 无表（p10-0 R7 以 epoch 投影代）
       ⇒ 25 类无一以它为残件

纪律：只读两半的权威常量与 `test_` 函数 docstring + canonical 原文；**不改** A/B 两半
文件（本刀只改 p10-2 的 `epoch-race-turn-canonicalize` 一段，另见该文件与
DEC-OPI-8f27d1de-…9）；本文件零 SQL、零 fixture、零 `_seed()`；零迁移；未触碰
`migrations/`、`docs/`（只读）、`behavioral_baselines/`、`tests/architecture/`、
`tests/conftest.py`、`registry.py`、`tests/phase9/`。
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass

from tests.conftest import DOCS_ROOT
from tests.phase10 import test_p10_1_failure_scenarios_a as a_half
from tests.phase10 import test_p10_2_failure_scenarios_b as b_half

#: A 半的行按源字面量落在 RA §23 五格内；B 半的行不属崩溃 checkpoint。
RA_23 = "RA_23"
CP4_AFTER_CANONICAL = "CP4-canonical-then"
NOT_A_CRASH_WINDOW = "—（B 半：进程未崩，不属 RA §23 五 checkpoint）"

#: RA §22 的第八类（IP §11 七类之外；两条语句由
#: ``test_the_two_vocabularies_are_read_off_canonical`` 现读现证）。
RA_22_ONLY_CLASS = "ServerDeliveryRecord"

IP_PLAN = DOCS_ROOT / "IMPLEMENTATION_PLAN.md"
RUNTIME_ARCHITECTURE = DOCS_ROOT / "RUNTIME_ARCHITECTURE.md"
IP_11_HEADING = "## 11. Detail Block — Runtime Recovery（Post-BF Phase 10）"
RA_22_HEADING = "## 22. Recovery"
RA_23_HEADING = "## 23. Recovery Checkpoints"

#: 扫面类名 → 它在**源文件残件字面量**里必然出现的判别词（大小写不敏感）。
#: 这张表覆盖 vocabulary 的每一项（由词汇测试核）。
SCAN_KEYWORDS: dict[str, str] = {
    "non-terminal TurnRecord": "TurnRecord",
    "GenerationActionIntent": "GenerationActionIntent",
    "TeachingMoment": "TeachingMoment",
    "TeachingLockLease": "lock",
    "ConversationCoordinatorLease": "lease",
    "pending AnalysisArtifact": "AnalysisArtifact",
    "pending projections": "projections",
    RA_22_ONLY_CLASS: "ServerDeliveryRecord",
}

#: 表末登记（编号, 钉用短句）——短句在模块 docstring 里逐条出现（文本一致，
#: 见 docstring 的 F2 能力边界：这不是语义真值的证明）。
REGISTRATIONS: tuple[tuple[str, str], ...] = (
    ("R1", "场景 8 的 §22 行在和解后仍未 terminal_at 冻结"),
    ("R2", "F2：本钉保证文本一致与命名覆盖，不校验表与测试体的语义真值"),
    ("R3", "6 类的 (i) 以弱形态钉"),
    ("R4", "②侧世界无 pending 行"),
    ("R5", 'RA §18 首句 "cancel current stream if possible"'),
    ("R6", "「封闭列表」是读法"),
    ("R7", "两裁定的重开条件写在模块内"),
    ("N1", "13 号的 checkpoint 字面量不在 RA §23 五格内"),
    ("N2", "A 半模块级 (ii) 行与 8/9/10 逐类文本的措辞差异"),
    ("N3", "ConversationCoordinatorLease 在 Local V1 无表"),
)


@dataclass(frozen=True)
class PhaseClass:
    """One of the phase's 25 failure classes as the phase-level table reads it.

    ``checkpoint`` and ``invariants`` are *declared classifications* this table
    asserts against values it derives from the source files (the source
    literals are never re-typed here; the walker looks them up); ``scan_class``
    is the IP §11 scan name the class is about, ``None`` meaning "no single
    name" with ``scan_note`` saying why.
    """

    tag: str
    half: str
    checkpoint: str
    scan_class: str | None
    scan_note: str
    invariants: tuple[str, str, str, str]


#: 25 类逐类一行；列序 = (tag, half, checkpoint, scan_class, scan_note, 四问类别)。
PHASE_CLASSES: tuple[PhaseClass, ...] = (
    # -- A 半：CP0–CP3 崩溃窗口 13 类（源：a_half.SCENARIOS） ------------------
    PhaseClass("CP0-crash-turn", "A", RA_23, "non-terminal TurnRecord",
               "单类（CP0 的 turn 残件）", ("适用", "适用", "适用", "N/A")),
    PhaseClass("CP0-crash-analysis", "A", RA_23, "pending AnalysisArtifact",
               "单类", ("适用", "适用", "适用", "N/A")),
    PhaseClass("CP1-crash-teaching", "A", RA_23, "non-terminal TurnRecord",
               "单类（命令 turn 的重入入口）", ("适用", "N/A", "适用", "N/A")),
    PhaseClass("CP1-crash-persona", "A", RA_23, "non-terminal TurnRecord",
               "单类（重入被拒）", ("适用", "N/A", "适用", "N/A")),
    PhaseClass("CP2-crash-action", "A", RA_23, "GenerationActionIntent",
               "单类", ("适用", "适用", "适用", "N/A")),
    PhaseClass("CP2-crash-moment-opening", "A", RA_23, "TeachingMoment",
               "两类同现（Moment + Lock，两个事实两个 apply 面）",
               ("N/A", "适用", "适用", "适用")),
    PhaseClass("CP2-crash-orphan-lock", "A", RA_23, "TeachingLockLease",
               "单类", ("N/A", "N/A", "适用", "N/A")),
    PhaseClass("CP3-under-record", "A", RA_23, RA_22_ONLY_CLASS,
               "RA §22 第八类（IP §11 七类之外）",
               ("适用", "N/A", "适用", "适用")),
    PhaseClass("CP3-no-blind-replay", "A", RA_23, "non-terminal TurnRecord",
               "两类同现（TurnRecord + RA §22 第八类）",
               ("适用", "N/A", "适用", "适用")),
    PhaseClass("CP3-partial-prefix", "A", RA_23, "non-terminal TurnRecord",
               "两类同现（TurnRecord + RA §22 第八类）",
               ("适用", "N/A", "适用", "适用")),
    PhaseClass("terminal-resume-fail", "A", RA_23, "TeachingMoment",
               "两类同现（Moment + Turn）", ("N/A", "N/A", "适用", "适用")),
    PhaseClass("terminal-teaching-then-reply", "A", RA_23, "TeachingMoment",
               "两类同现（Moment + Lock）", ("N/A", "适用", "适用", "适用")),
    PhaseClass("projection-crash-gap", "A", CP4_AFTER_CANONICAL,
               "pending projections", "单类（CP4 窗口，不在 §23 五格内 —— N1）",
               ("N/A", "适用", "适用", "N/A")),
    # -- B 半：非崩溃失败 12 类（源：b_half.SCENARIOS + INVARIANTS） -----------
    PhaseClass("degraded-learning-leg", "B", NOT_A_CRASH_WINDOW,
               "pending AnalysisArtifact", "单类（降级留下一枚 pending 残件）",
               ("适用", "适用", "适用", "N/A")),
    PhaseClass("degraded-projection-line", "B", NOT_A_CRASH_WINDOW,
               "pending projections", "单类", ("N/A", "适用", "适用", "N/A")),
    PhaseClass("degraded-ledger-write", "B", NOT_A_CRASH_WINDOW, None,
               "§20 曝光事件 —— 不在 §11 七类 / §22 八类扫面清单里（B 半原表同读法）",
               ("适用", "适用", "适用", "适用")),
    PhaseClass("scan-read-failure", "B", NOT_A_CRASH_WINDOW, None,
               "四类扫面本身（不是某一类残件）", ("适用", "适用", "适用", "N/A")),
    PhaseClass("epoch-race-action-claim", "B", NOT_A_CRASH_WINDOW,
               "GenerationActionIntent", "单类", ("适用", "适用", "适用", "N/A")),
    PhaseClass("epoch-race-turn-canonicalize", "B", NOT_A_CRASH_WINDOW,
               "non-terminal TurnRecord", "单类（turn + transcript）",
               ("适用", "适用", "适用", "N/A")),
    PhaseClass("late-callback-foreign-epoch", "B", NOT_A_CRASH_WINDOW,
               "GenerationActionIntent", "单类", ("适用", "适用", "适用", "适用")),
    PhaseClass("late-callback-cancelled", "B", NOT_A_CRASH_WINDOW,
               RA_22_ONLY_CLASS, "RA §22 第八类（IP §11 七类之外）",
               ("适用", "适用", "适用", "适用")),
    PhaseClass("multi-residue-coexist", "B", NOT_A_CRASH_WINDOW, None,
               "六类同现（无单一扫面名）", ("适用", "适用", "适用", "适用")),
    PhaseClass("residue-then-normal-turn", "B", NOT_A_CRASH_WINDOW, None,
               "两类同现（Lock + Moment）", ("适用", "适用", "适用", "适用")),
    PhaseClass("interrupt-during-recovery", "B", NOT_A_CRASH_WINDOW, None,
               "§17.1 输入行（不在 §11 / §22 扫面清单里）",
               ("适用", "适用", "适用", "适用")),
    PhaseClass("idempotent-second-startup", "B", NOT_A_CRASH_WINDOW, None,
               "六类同现（幂等重跑）", ("适用", "适用", "适用", "N/A")),
)

_MARKER = re.compile(r"\((i|ii|iii|iv)\)")
_ORDER = ("i", "ii", "iii", "iv")


def _section_lines(text: str, heading: str) -> list[str]:
    """Every line between ``heading`` and the next same-level (``## ``) heading."""

    lines = text.splitlines()
    start = next(
        (index for index, line in enumerate(lines) if line.strip() == heading),
        None,
    )
    assert start is not None, f"heading {heading!r} not found"
    body: list[str] = []
    for line in lines[start + 1:]:
        if line.startswith("## ") or line.startswith("# "):
            break
        body.append(line)
    return body


def _fenced_blocks(body: list[str]) -> list[tuple[str, ...]]:
    """The fenced blocks of one section, blank lines dropped."""

    blocks: list[tuple[str, ...]] = []
    current: list[str] | None = None
    for line in body:
        if line.startswith("```"):
            if current is None:
                current = []
            else:
                blocks.append(tuple(current))
                current = None
            continue
        if current is not None and line.strip():
            current.append(line.strip())
    return blocks


def ip_11_scan_classes() -> tuple[str, ...]:
    """IP §11's scan classes: the first fenced block after its heading
    (the ``Recovery worker 扫`` list)."""

    body = _section_lines(
        IP_PLAN.read_text(encoding="utf-8"), IP_11_HEADING
    )
    blocks = _fenced_blocks(body)
    assert blocks, "IP §11: no fenced block"
    return blocks[0]


def ra_22_scan_classes() -> tuple[str, ...]:
    """RA §22's recovery list (the eight items; IP §11 lists seven)."""

    body = _section_lines(
        RUNTIME_ARCHITECTURE.read_text(encoding="utf-8"), RA_22_HEADING
    )
    blocks = _fenced_blocks(body)
    assert blocks, "RA §22: no fenced block"
    return blocks[0]


def ra_23_checkpoints() -> tuple[str, ...]:
    """RA §23's checkpoints: its ``###`` headings, in order."""

    body = _section_lines(
        RUNTIME_ARCHITECTURE.read_text(encoding="utf-8"), RA_23_HEADING
    )
    return tuple(line[4:].strip() for line in body if line.startswith("### "))


def _matching_tests(module: object, tag: str) -> list[str]:
    """The ``test_`` functions of one half whose name starts with the tag's slug."""

    slug = tag.replace("-", "_").lower()
    return [
        name
        for name, value in vars(module).items()
        if name.startswith(f"test_{slug}") and callable(value)
    ]


def _head_word(segment: str) -> str:
    """``适用`` / ``N/A`` off one ``(k) <answer>`` segment, however it wraps."""

    head = segment.split("：")[0].split("，")[0].strip()
    if head.startswith("适用"):
        return "适用"
    assert head.startswith("N/A"), segment[:60]
    return "N/A"


def _invariant_classes(doc: str) -> tuple[str, str, str, str]:
    """The four applicability classes, read off one class test's docstring.

    The shared-answer shape (``(i)(ii) 适用：…``) gives the first marker an empty
    segment, so an empty segment inherits the next non-empty one — that is the
    docstring's own convention, not a guess.
    """

    marks = list(_MARKER.finditer(doc))
    assert marks, "no (i)-(iv) answers in the docstring"
    segments: dict[str, str] = {}
    for index, mark in enumerate(marks):
        end = marks[index + 1].start() if index + 1 < len(marks) else len(doc)
        segments[mark.group(1)] = " ".join(doc[mark.end():end].split())
    classes: list[str] = []
    for position, key in enumerate(_ORDER):
        segment = segments.get(key, "")
        if not segment:
            for later in _ORDER[position + 1:]:
                if segments.get(later):
                    segment = segments[later]
                    break
        assert segment, key
        classes.append(_head_word(segment))
    return (classes[0], classes[1], classes[2], classes[3])


# -- the walker ---------------------------------------------------------------


def test_the_phase_table_walks_all_twenty_five_classes_once_each() -> None:
    """The one test that walks the table row by row.

    ① tag 集：25 行、tag 唯一、A 半 13 与 B 半 12 各自**集合相等**（每文件无 tag
    逃出表外、表里没有源文件不认的 tag）；② 每 tag 在**它自己的源文件**里唯一命中
    一个 `test_` 函数；③ checkpoint：A 行按源字面量落在 RA §23 五格（现读标题）或
    第六格（N1），B 行是哨兵；④ 四项不变量：A 行 = 该 tag 自己 docstring 的现读分类、
    B 行 = `INVARIANTS` 短答的现读头词；⑤ 扫面：非 `None` 者必在词汇内且其判别词出现
    在**源文件**的残件字面量里，`None` 者 `scan_note` 非空；⑥ 五格每格至少一个 tag
    见证，且第六格恰一个。
    """

    a_tags = [tag for tag, _, _, _ in a_half.SCENARIOS]
    b_tags = [tag for tag, _, _ in b_half.SCENARIOS]
    assert len(a_tags) == 13 and len(set(a_tags)) == 13
    assert len(b_tags) == 12 and len(set(b_tags)) == 12
    assert set(b_tags) == set(b_half.INVARIANTS)

    rows = PHASE_CLASSES
    assert len(rows) == 25
    assert len({row.tag for row in rows}) == 25
    assert {row.tag for row in rows if row.half == "A"} == set(a_tags)
    assert {row.tag for row in rows if row.half == "B"} == set(b_tags)

    a_literals = {tag: (cp, residue) for tag, cp, residue, _ in a_half.SCENARIOS}
    b_literals = {tag: residue for tag, residue, _ in b_half.SCENARIOS}
    checkpoints = ra_23_checkpoints()
    vocabulary = ip_11_scan_classes()

    for row in rows:
        assert len(_matching_tests(a_half if row.half == "A" else b_half,
                                  row.tag)) == 1, row.tag
        if row.half == "A":
            checkpoint, residue = a_literals[row.tag]
            expected = RA_23 if checkpoint in checkpoints else CP4_AFTER_CANONICAL
            assert row.checkpoint == expected, row.tag
            test_name = _matching_tests(a_half, row.tag)[0]
            doc = getattr(a_half, test_name).__doc__ or ""
            assert row.invariants == _invariant_classes(doc), row.tag
        else:
            assert row.checkpoint == NOT_A_CRASH_WINDOW, row.tag
            residue = b_literals[row.tag]
            answers = b_half.INVARIANTS[row.tag]
            heads = tuple(_head_word(answer) for answer in answers)
            assert row.invariants == heads, row.tag
        assert row.invariants and len(row.invariants) == 4, row.tag
        assert all(word in {"适用", "N/A"} for word in row.invariants), row.tag
        if row.scan_class is None:
            assert row.scan_note, row.tag
        else:
            assert row.scan_class in vocabulary + (RA_22_ONLY_CLASS,), row.tag
            keyword = SCAN_KEYWORDS[row.scan_class].lower()
            assert keyword in residue.lower(), (row.tag, keyword, residue)

    witnessed = {a_literals[row.tag][0] for row in rows if row.half == "A"}
    assert set(checkpoints) <= witnessed, "every RA §23 checkpoint has a class"
    assert len(witnessed - set(checkpoints)) == 1, witnessed  # the CP4 sixth (N1)
    assert len(checkpoints) == 5


def test_the_two_vocabularies_are_read_off_canonical() -> None:
    """The seven scan classes and the five checkpoints are not recalled from
    memory in this file: they are read off canonical, and the eighth scan class
    is registered as RA §22's own (present there, absent from IP §11)."""

    scans = ip_11_scan_classes()
    assert len(scans) == 7
    assert len(set(scans)) == 7
    assert all(scans)

    ra_22 = ra_22_scan_classes()
    assert len(ra_22) == 8
    assert RA_22_ONLY_CLASS in ra_22
    assert RA_22_ONLY_CLASS not in scans

    checkpoints = ra_23_checkpoints()
    assert len(checkpoints) == 5
    assert len(set(checkpoints)) == 5
    assert all(checkpoints)

    # the keyword table covers exactly the vocabulary this file's rows may name
    assert set(SCAN_KEYWORDS) == set(scans) | {RA_22_ONLY_CLASS}


def test_the_registration_tail_and_the_f2_boundary_are_in_the_module_text() -> None:
    """The tail's entries and the F2 capability boundary are the module's own
    words — each registration's pin phrase and the boundary's phrases have to
    be *in* the docstring, so a later cut cannot drop one silently.

    Registered limit: this is a phrase-existence pin (text consistency), not a
    statement that the entries are true — see the docstring's F2 boundary.
    """

    doc = sys.modules[__name__].__doc__ or ""
    ids = [rid for rid, _ in REGISTRATIONS]
    assert ids == [f"R{i}" for i in range(1, 8)] + ["N1", "N2", "N3"]
    for rid, phrase in REGISTRATIONS:
        assert phrase in doc, (rid, phrase)
    assert "F2 能力边界" in doc
    assert "文本一致与命名覆盖" in doc
    assert "不校验" in doc and "语义真值" in doc
    assert "不得引用为「表与测试体一致」的机器证明" in doc
