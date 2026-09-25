"""P9-5 C — honesty: the coverage map, the registrations, and what this cut is.

Four claims, all checkable in the shipped tree:

- **the nine promises map to nine real tests**: the map is a module constant,
  and the test below does not trust it — it runs the collector over the sibling
  module in a subprocess and asserts every mapped name is **collected** (the
  p8-5 precedent, which runs a cold interpreter for its own import claim), plus
  that the map is total over :data:`PROMISES` and injective (one promise, one
  test — a single test covering several promises is exactly what the task
  forbids);
- **the map is not the whole truth, and says so**: :data:`UNTESTABLE_TODAY`
  registers what these nine do *not* prove — each entry carries why it cannot
  be proven today and what would make it provable — and the test asserts every
  registered item is absent from the map (a registration may not be smuggled
  into a coverage claim);
- **the package has no skip and no xfail**: every ``tests/phase9/*.py`` is
  scanned as text for the four marker spellings, so "0 skipped" is a fact about
  the source rather than about one run's summary line;
- **this cut adds tests and only tests**: the three files are named as a
  constant, they exist, they are the only ``test_p9_5_*.py`` in the package,
  and no file under ``src/`` or ``migrations/`` carries this cut's name — the
  P8-5 shape for "no source was touched", checkable without a VCS.

The scan for a vacuous assertion (a short-circuit tail that makes the line true
whatever the left side says, or a bare assertion of truth) is the one mechanical
guard against a test that cannot fail; it is deliberately narrow, because a
broader pattern list would start rejecting honest assertions. The marker
spellings are built from parts so that this file's own text does not contain
them — otherwise the scan's first finding would always be itself.
"""

from __future__ import annotations

import ast
import inspect
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT, SRC_ROOT
from tests.phase9 import test_p9_5_e2e as e2e_module
from tests.phase9 import test_p9_5_promise_list as promise_module
from tests.phase9.test_p9_5_promise_list import PROMISES

PHASE9 = REPO_ROOT / "tests" / "phase9"

#: The three files this cut adds — the whole delivery面 of a tests-only cut.
NEW_FILES: tuple[str, ...] = (
    "test_p9_5_promise_list.py",
    "test_p9_5_e2e.py",
    "test_p9_5_honesty.py",
)

#: promise (verbatim, as :data:`PROMISES` spells it) → the one test that holds
#: it. The names are checked against the collector's own output below, so this
#: table cannot drift into a hand-written claim.
PROMISE_TESTS: dict[str, str] = {
    PROMISES[0]: (
        "test_promise_1_a_partial_send_is_never_recorded_as_full_exposure"
    ),
    PROMISES[1]: (
        "test_promise_2_without_an_ack_the_certainty_stays_server_sent_unconfirmed"
    ),
    PROMISES[2]: (
        "test_promise_3_a_late_ack_raises_certainty_only_and_writes_no_mastery"
    ),
    PROMISES[3]: (
        "test_promise_4_the_unsent_tail_of_a_barge_in_is_nowhere_in_the_transcript"
    ),
    PROMISES[4]: (
        "test_promise_5_a_late_callback_after_cancellation_leaves_no_canonical"
        "_side_effect"
    ),
    PROMISES[5]: (
        "test_promise_6_a_terminal_action_over_a_delivering_turn_reconciles"
        "_conservatively"
    ),
    PROMISES[6]: (
        "test_promise_7_a_presented_teaching_action_owes_exactly_one_exposure_event"
    ),
    PROMISES[7]: (
        "test_promise_8_a_delivery_that_sent_nothing_claims_no_exposure"
    ),
    PROMISES[8]: (
        "test_promise_9_duplicate_reconciliation_writes_no_duplicate"
    ),
}

#: The two chains the E2E module drives, by test name.
E2E_TESTS: tuple[str, ...] = (
    "test_the_guarded_stream_chat_chain_step_by_step",
    "test_the_buffered_teaching_chain_step_by_step",
)

#: What these nine promises do **not** prove today, and what would change that.
#: Registered rather than covered: each entry names a fact a reader might
#: reasonably expect the九条 to settle, the reason it cannot be settled in this
#: tree, and the trigger that would give it a carrier.
UNTESTABLE_TODAY: dict[str, tuple[str, str]] = {
    "a real delivery channel / a real client render acknowledgment": (
        "V1 has no out-of-process transport: ``stream_transport`` is the"
        " assembly's injection point and the shipped default releases the"
        " validated text as one in-process chunk, while ``accept_render_ack``"
        " is called by a caller rather than driven by a renderer. The nine"
        " promises are therefore about the *server* half — what the durable"
        " row and the estimate do with an acknowledgment — and no test here"
        " can claim a real renderer sent one.",
        "a cut wires a real transport (then the ACK gains a producer and the"
        " mapping needs no change).",
    ),
    "a real process crash": (
        "both crash windows are built by a refused write (the first"
        " ``terminalize_turn`` and the first ``run_action``), which leaves the"
        " same durable residue a killed process would, but the recovery runs"
        " in-process on the same file. What is proven is the *residue's* shape"
        " and the reconciliation's conservatism, not the death itself.",
        "a cut adds a subprocess-kill harness (then the same residue can be"
        " produced by an actual death).",
    ),
    "the mastery-independence pin against a non-empty mastery table": (
        "the nine mastery/evidence/attempt tables are empty in the teaching"
        " world these tests build (the shipped chain commits no Evidence on an"
        " opening delivery), so promise 3's assertion is a **write set**:"
        " exactly one row appeared, in ``client_render_ack``. The mutation that"
        " makes the acknowledgment write a mastery row turns it red (receipt"
        " ⑨), which is what makes the pin load-bearing — but a reader should"
        " know the rows are not there to be raised.",
        "a world where a real Evidence commit precedes the delivery (P5's"
        " silent-evidence chain) — then the same diff runs against a non-empty"
        " table.",
    ),
    "a barge-in landing in the same window as the stream's last chunk": (
        "``controller._cancel_streamed_delivery`` registers this race"
        " (P9-3 review INFO-1): every chunk released, the terminal freeze not"
        " yet written, the cancellation reading the run — the whole text is"
        " durable yet the row freezes ``CANCELLED`` and the transcript spells"
        " ``SENT_PARTIAL``. Promise 4's two cut points are *before* that window"
        " and do not reach it.",
        "a cut that makes the window reachable through a shipped face (or"
        " pins the registered reading with a deliberately forced row).",
    ),
    "a hint or a reveal delivery's own exposure event": (
        "the ALLOW chain these tests drive presents one **opening**; §20's"
        " ``hint_presented`` / ``reveal_presented`` travel through the same"
        " writer (``LEDGER_EVENT_BY_DELIVERY``) but reaching them needs a"
        " second turn inside a live moment, which the nine promises do not"
        " require and this file does not claim.",
        "a cut that walks a live moment from ``AWAITING_USER`` through a hint"
        " or a reveal (the writer is already total over the three kinds).",
    ),
}

#: Every spelling of a skipped test the package is scanned for. Built from
#: parts on purpose: this file contains these constants, and a scan whose first
#: finding is the scanner would be useless.
SKIP_MARKERS: tuple[str, ...] = (
    "pytest" + ".skip",
    "pytest" + ".mark.skip",
    "pytest" + ".mark.xfail",
    "pytest" + ".importorskip",
)

#: The spellings of a vacuous assertion the new files are scanned for (the same
#: build-from-parts rule).
WEAK_MARKERS: tuple[str, ...] = (
    " or " + "True",
    "assert " + "True",
    "assert not " + "False",
    " is not None or " + "True",
)


# -- ① the coverage map, checked against the collector -------------------------


def _collected_ids() -> set[str]:
    """The test ids the collector itself reports for this cut's two files.

    A subprocess rather than an in-process import: the claim being checked is
    "pytest *collects* this", and a green import says less than that. The
    ``-o addopts=""`` is the repository's own fact — ``pyproject.toml`` sets
    ``-q`` as an addopt, and a second ``-q`` suppresses the per-id lines.
    """

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-o",
            'addopts=""',
            "tests/phase9/test_p9_5_promise_list.py",
            "tests/phase9/test_p9_5_e2e.py",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return {
        line.strip()
        for line in completed.stdout.splitlines()
        if "::" in line and line.strip().startswith("tests/")
    }


def test_the_map_is_total_and_injective_over_the_nine_promises() -> None:
    """Nine promises, nine entries, nine different tests — the map's own
    arithmetic, before the collector is asked anything."""

    assert len(PROMISES) == 9
    assert list(PROMISE_TESTS) == list(PROMISES)  # same key order, verbatim
    names = list(PROMISE_TESTS.values())
    assert len(set(names)) == 9, "one test cannot hold two promises"
    for name in names:
        assert name.startswith("test_"), name
        assert getattr(promise_module, name, None) is not None, name


def test_every_mapped_name_is_collected_by_pytest() -> None:
    """The map is not a hand-written claim: the collector's own output contains
    every name it names, and the two chains are collected too."""

    collected = _collected_ids()
    assert collected, "the collector reported no test ids at all"
    for promise, name in PROMISE_TESTS.items():
        assert any(
            identifier.endswith(f"::{name}") or f"::{name}[" in identifier
            for identifier in collected
        ), f"{promise!r} → {name} was not collected"
    for name in E2E_TESTS:
        assert any(
            identifier.endswith(f"::{name}") or f"::{name}[" in identifier
            for identifier in collected
        ), name
    # and the honesty module itself is collected (it carries the map)
    assert (PHASE9 / "test_p9_5_honesty.py").exists()


def test_the_two_chains_exist_in_the_e2e_module() -> None:
    for name in E2E_TESTS:
        assert callable(getattr(e2e_module, name, None)), name


@pytest.mark.parametrize("promise", PROMISES)
def test_each_promise_is_quoted_verbatim_in_its_own_tests_docstring(
    promise: str,
) -> None:
    """R2's first half, mechanically: the promise is a **verbatim** quote in
    the docstring of the one test that holds it, so the mapping is a quotation
    rather than a paraphrase. Nine parametrized cases, one per promise."""

    name = PROMISE_TESTS[promise]
    test = getattr(promise_module, name)
    docstring = inspect.getdoc(test)
    assert docstring is not None, name
    assert promise in docstring, f"{name} does not quote {promise!r} verbatim"
    # and the docstring declares the durable evidence it rests on
    assert "Evidence:" in docstring or "Evidence" in docstring, name


def test_the_two_chains_declare_their_steps() -> None:
    """R3's other half: each chain's docstring carries its **step list**, so the
    chain is declared rather than implied — and the first step is CP0 in both,
    which is the pipeline's own first commit point."""

    for name in E2E_TESTS:
        docstring = inspect.getdoc(getattr(e2e_module, name))
        assert docstring is not None, name
        assert "**CP0**" in docstring, name
        steps = [
            number
            for number in range(1, 13)
            if f"{number}. **" in docstring
        ]
        assert steps == list(range(1, len(steps) + 1)), (name, steps)
        assert len(steps) >= 6, (name, steps)


# -- ② the registrations -------------------------------------------------------


def test_each_registration_carries_a_reason_and_a_trigger() -> None:
    assert len(UNTESTABLE_TODAY) >= 4, "a cut that claims full coverage is lying"
    for item, (reason, trigger) in UNTESTABLE_TODAY.items():
        assert item.strip(), item
        assert len(reason) > 80, item  # why it cannot be proven today
        assert len(trigger) > 30, item  # what would make it provable


def test_no_registration_is_smuggled_into_the_coverage_map() -> None:
    """The closure that makes the map a coverage claim rather than a subset: the
    promise module carries **exactly** the nine mapped tests and nothing else,
    and no registered subject is spelled as one of the promises."""

    tree = ast.parse(
        Path(promise_module.__file__).read_text(encoding="utf-8")
    )
    names = sorted(
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    )
    assert names == sorted(PROMISE_TESTS.values())
    for item in UNTESTABLE_TODAY:
        assert item not in PROMISES, item
        assert item not in " | ".join(PROMISE_TESTS.values()), item


# -- ③ zero skip, zero vacuous assertion ---------------------------------------


def test_no_file_in_this_package_carries_a_skip_or_an_xfail() -> None:
    """The task's zero-skip rule, as a fact about the source: no file in
    ``tests/phase9/`` spells a skip, an xfail or an import-orskip."""

    offenders: dict[str, list[str]] = {}
    scanned = 0
    for path in sorted(PHASE9.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        scanned += 1
        found = [marker for marker in SKIP_MARKERS if marker in text]
        if found:
            offenders[path.name] = found
    assert scanned >= 18, f"only {scanned} files scanned in {PHASE9}"
    assert offenders == {}, offenders


def test_the_new_files_carry_no_vacuous_assertion() -> None:
    """The narrow mechanical guard against a test that cannot fail: neither a
    short-circuit tail that makes the line true whatever the left side says,
    nor a bare assertion of truth, in this cut's three files."""

    offenders: dict[str, list[str]] = {}
    for name in NEW_FILES:
        text = (PHASE9 / name).read_text(encoding="utf-8")
        found = [marker for marker in WEAK_MARKERS if marker in text]
        if found:
            offenders[name] = found
    assert offenders == {}, offenders

    # the check itself is not vacuous: every test in the two new modules has a
    # body, and the promise tests each carry at least one assert
    for module in (promise_module, e2e_module):
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        tests = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
        ]
        assert tests, module.__name__
        for node in tests:
            asserts = [
                child
                for child in ast.walk(node)
                if isinstance(child, ast.Assert)
            ]
            assert asserts, f"{module.__name__}::{node.name} has no assertion"


# -- ④ this cut adds tests, and only tests -------------------------------------


def test_the_three_new_files_are_this_cuts_and_are_all_tests() -> None:
    for name in NEW_FILES:
        path = PHASE9 / name
        assert path.exists(), name
        assert path.read_text(encoding="utf-8").startswith('"""'), name
    # they are the only files this cut names, and the package's own set is the
    # older suites plus exactly these three
    assert sorted(
        path.name for path in PHASE9.glob("test_p9_5_*.py")
    ) == sorted(NEW_FILES)


def test_no_source_file_carries_this_cuts_name() -> None:
    """A tests-only cut: neither ``src/`` nor ``migrations/`` gained a file
    whose name carries the p9-5 tag (the P8-5 shape for "no source was
    touched", checkable without a VCS)."""

    tagged = [
        str(path.relative_to(REPO_ROOT))
        for path in list(SRC_ROOT.rglob("*p9_5*"))
        + list(SRC_ROOT.rglob("*p9-5*"))
        + list((REPO_ROOT / "migrations").rglob("*p9_5*"))
        + list((REPO_ROOT / "migrations").rglob("*p9-5*"))
    ]
    assert tagged == [], tagged
    # and the migration head this cut was told not to move is still the one
    assert sorted(
        path.name for path in (REPO_ROOT / "migrations").glob("*.sql")
    )[-1] == "0018_delivery_records.sql"


def test_the_frozen_surfaces_are_read_not_written() -> None:
    """The three frozen trees (the canonical docs, the behavioural baselines
    and the architecture tests) are read here — never written — and the two
    migration facts this cut was told not to move are pinned."""

    for relative in (
        "docs/IMPLEMENTATION_PLAN.md",
        "docs/RUNTIME_ARCHITECTURE.md",
        "docs/STATE_MACHINES.md",
        "behavioral_baselines/gate/BF-03_Teaching_Gate_Decision_Spec_v1.0.md",
        "behavioral_baselines/gate/teaching_gate_benchmark_v1.json",
        "behavioral_baselines/planner/planner_stress_cases_v1_1.json",
    ):
        assert (REPO_ROOT / relative).exists(), relative
    # the §10 block this cut's two chains come from, verbatim
    plan = (REPO_ROOT / "docs" / "IMPLEMENTATION_PLAN.md").read_text(
        encoding="utf-8"
    )
    assert "## 10. Detail Block — Delivery / Exposure Hardening" in plan
    for line in (
        "- partial reveal 不被记为 full exposure",
        "- no ACK 使用 conservative support",
        "- barge-in 旧 tail 不进入 transcript",
        "- late provider result 无副作用",
    ):
        assert line in plan, line
