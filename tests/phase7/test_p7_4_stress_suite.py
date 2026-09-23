"""P7-4 ②③④ — BF-02's frozen 43-case stress suite, replayed in-repo.

The replay lives in :mod:`elc.planner.stress_suite`; what is pinned here is that
it reproduces the frozen file's own expectations **exactly**, that the three
divergences P7-1 registered are modelled at the adapter boundary, and that the
frozen assets are read rather than depended on:

- **43/43 with zero divergences**, one printable line per case, and the six
  ``error: true`` cases refused *for the condition their own description names*
  rather than for "some error";
- **the three registered divergences**, each by its own claim: S04 refuses on
  the duplicate ``canonical_key`` while the kernel still merges that shape as
  proposals; S42 refuses on the duplicate ``id`` (the id checked first); S20 is
  ``DEGRADED`` because BF-02 §5's two words are read before the kernel, while
  the kernel keeps §10.1's order and refuses the same short vector when handed
  it directly;
- **the reference stays read-only**: the two frozen copies of
  ``planner_reference_v1_1.py`` are byte-identical and nothing under ``src/``
  imports either one (the replay reads the *cases*, never the reference
  implementation);
- **the replay cannot pass by construction**: a tampered expectation shows up as
  a divergence, and the case file is unchanged by a full run.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import re
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from elc.planner import kernel, stress_suite
from elc.planner.kernel import PlannerInputError, plan
from elc.planner.stress_suite import (
    CASE_CUSTOM_WORDS,
    STRESS_SUITE_MODEL_VERSION,
    CaseKind,
    degraded_reason_of,
    load_cases,
    planning_input_of,
    proposals_of,
    run_input,
    schedule_row_of,
    stress_report,
    stress_table,
    verdict_of,
)
from elc.scheduler.types import ScheduleItem
from tests.conftest import BASELINES, REPO_ROOT

from .conftest import kernel_input, proposal, source_text

CASES_PATH = BASELINES / "planner" / "planner_stress_cases_v1_1.json"
RUNNER_PATH = BASELINES / "planner" / "run_stress.py"
REFERENCE_COPIES = (
    BASELINES / "planner" / "planner_reference_v1_1.py",
    BASELINES / "golden" / "planner_reference_v1_1.py",
)
SUITE_MODULE = "src/elc/planner/stress_suite.py"

#: The frozen file's 43 case ids, in its own order — the suite's identity, so a
#: swapped or truncated file fails here rather than in a silent 43/43.
FROZEN_IDS = (
    "S01_MULTI_MANUAL_PRIORITY",
    "S02_COMMUNICATIVE_IMPACT",
    "S03_PARETO",
    "S04_DUPLICATE_CANONICAL",
    "S05_AUTH_UNAVAILABLE",
    "S06_STALE_SNAPSHOT",
    "S07_JUSTCHAT_CONTRADICTION",
    "S08_RUNTIME_READY_AUTO_ERROR",
    "S09_RUNTIME_READY_AUTO_GENERAL",
    "S10_RUNTIME_READY_USER",
    "S11_SCAFFOLD_COST",
    "S12_COVERAGE_STARVATION",
    "S13_DEBT_SCOPE",
    "S14_DEBT_JUSTCHAT",
    "S15_BLOCKING_ERROR_VS_REVIEW",
    "S16_LOW_ERROR_VS_REVIEW",
    "S17_REQUEST_BINDING",
    "S18_EQUAL_REQUEST_PRIORITY",
    "S19_PROTECTED_GATE_BOUNDARY",
    "S20_MISSING_FACTOR_DEGRADE",
    "S21_ORIGIN_NO_SCORE",
    "S22_TARGET_SCOPE",
    "S23_R2_ORDINARY",
    "S24_R2_PROBE",
    "S25_SOFT_RESISTANCE",
    "S26_SUPPRESSION",
    "S27_POLICY_LOUNGE",
    "S28_POLICY_STUDY",
    "S29_BENEFIT_MONOTONIC",
    "S30_COST_MONOTONIC",
    "S31_ORDER",
    "S32_DEBT_LOUNGE",
    "S33_CONTEXT_META_VALID",
    "S34_HARD_PREREQ",
    "S35_UNKNOWN_SCAFFOLD",
    "S36_EXPIRED",
    "S37_DEPRECATED",
    "S38_MODALITY",
    "S39_GATE_BOUNDARY",
    "S40_EXPLICIT_OVERRIDES_SOFT_RESISTANCE",
    "S41_INVALID_MODE_INTENT",
    "S42_DUP_ID",
    "S43_FACTOR_RANGE",
)

#: The six ``error: true`` cases and the condition each one's ``description``
#: names — the fragments its refusal has to carry, so "caught something" cannot
#: pass for "caught the thing the case is about".
REFUSAL_CONDITIONS = {
    "S04_DUPLICATE_CANONICAL": ("duplicate canonical_key", "'same'"),
    "S07_JUSTCHAT_CONTRADICTION": ("JUST_CHAT", "contradictory"),
    "S11_SCAFFOLD_COST": ("support_cost", "scaffold"),
    "S41_INVALID_MODE_INTENT": ("PROBE cannot carry DEVELOP",),
    "S42_DUP_ID": ("duplicate candidate id", "'x'"),
    "S43_FACTOR_RANGE": ("learning_need", "outside [0, 1]"),
}


def cases() -> tuple[dict[str, Any], ...]:
    return tuple(load_cases(CASES_PATH))


def case_of(case_id: str) -> dict[str, Any]:
    return next(case for case in cases() if case["id"] == case_id)


def raw_utilities(case_id: str) -> dict[str, float]:
    """The kernel's own (unrounded) utilities for one case's scored set."""

    result = plan(planning_input_of(case_of(case_id)["input"]))
    return {
        row.candidate_id: row.utility
        for row in result.trace.candidates
        if row.utility is not None
    }


# ---------------------------------------------------------------------------
# ② the 43/43 replay
# ---------------------------------------------------------------------------


def test_the_frozen_suite_is_43_cases_and_this_replay_matches_every_one() -> None:
    """The acceptance: one verdict per case, zero divergences, and the count the
    frozen file carries."""

    loaded = cases()
    assert len(loaded) == 43
    assert tuple(case["id"] for case in loaded) == FROZEN_IDS
    verdicts = stress_table(loaded)
    assert len(verdicts) == 43
    assert [verdict.line() for verdict in verdicts if not verdict.passed] == []
    assert sum(verdict.passed for verdict in verdicts) == 43
    assert tuple(verdict.case_id for verdict in verdicts) == FROZEN_IDS


def test_the_report_prints_one_line_per_case_and_a_total() -> None:
    """§8's "人工/测试审查" in printable form: 43 rows plus the total line."""

    report = stress_report(cases())
    lines = report.splitlines()
    assert len(lines) == 44
    assert lines[-1] == "BF-02 stress: 43/43 PASS"
    assert lines[0].startswith("S01_MULTI_MANUAL_PRIORITY")
    assert "SELECT z_primary" in lines[0]
    for line in lines[:43]:
        assert line.endswith("PASS"), line
    for case_id in FROZEN_IDS:
        assert any(
            line.startswith(case_id) for line in lines[:43]
        ), case_id


def test_the_replay_reads_the_kernels_own_numbers_rather_than_rescoring() -> None:
    """The ``scored`` column is the kernel's utilities (rounded the way the
    frozen runner rounds), not a second weighted sum."""

    for case_id in ("S01_MULTI_MANUAL_PRIORITY", "S12_COVERAGE_STARVATION"):
        run = run_input(case_of(case_id)["input"])
        raw = raw_utilities(case_id)
        assert dict(run.scored) == {
            candidate_id: round(utility, 6)
            for candidate_id, utility in raw.items()
        }


def test_the_frozen_runner_compares_the_predicates_this_module_reproduces() -> None:
    """The five custom words and the tolerance are read off the frozen runner
    itself, so the replica's branch list has one source."""

    runner = RUNNER_PATH.read_text(encoding="utf-8")
    for word in CASE_CUSTOM_WORDS:
        assert word in runner, word
    assert "1e-9" in runner
    assert 'e["error"]' in runner
    assert 'e["decision"]' in runner
    customs = {
        case["expected"]["custom"]
        for case in cases()
        if case["expected"]["custom"] is not None
    }
    assert customs == set(CASE_CUSTOM_WORDS)


def test_the_replay_changes_nothing_in_the_frozen_file_data() -> None:
    """A full table run leaves every case object where it found it — the
    ORDER_DETERMINISM branch examines a reversed order without mutating the
    case it came from."""

    loaded = cases()
    before = copy.deepcopy(loaded)
    stress_table(loaded)
    assert loaded == before


def test_a_tampered_expectation_is_a_divergence() -> None:
    """The replay cannot pass by construction: move one expectation and the
    table says so, with the answered result in the evidence."""

    tampered = json.loads(json.dumps(case_of("S01_MULTI_MANUAL_PRIORITY")))
    tampered["expected"]["selected"] = "a_secondary"
    verdict = verdict_of(tampered)
    assert not verdict.passed
    assert verdict.verdict_word == "DIVERGENCE"
    assert "SELECT z_primary" in verdict.evidence

    not_an_error = json.loads(json.dumps(case_of("S04_DUPLICATE_CANONICAL")))
    not_an_error["expected"]["error"] = False
    assert not verdict_of(not_an_error).passed

    degraded_but_decided = json.loads(json.dumps(case_of("S05_AUTH_UNAVAILABLE")))
    degraded_but_decided["expected"]["custom"] = "EQUAL_UTILITY"
    assert not verdict_of(degraded_but_decided).passed

    # The fourth direction, and the one the three above cannot make: a **non**
    # error case relabelled ``error: true``. The ``error`` arm is the single
    # branch that answers without reading the run, so its fail-closed side is
    # that "an error was expected" is satisfied only by a refusal — a case this
    # chain answered with a decision is a DIVERGENCE, never a pass.
    error_but_decided = json.loads(
        json.dumps(case_of("S12_COVERAGE_STARVATION"))
    )
    error_but_decided["expected"]["error"] = True
    verdict = verdict_of(error_but_decided)
    assert not verdict.passed
    assert verdict.verdict_word == "DIVERGENCE"
    assert verdict.kind is CaseKind.SELECT
    assert verdict.evidence == "SELECT debt"


def test_a_relabelled_error_in_a_file_turns_the_cli_total_red(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The same direction at the file level, which is where the failure mode
    lives: one *passing* case relabelled ``error: true`` in a copy of the
    frozen file. The CLI must answer a DIVERGENCE line for it and exit
    non-zero — never the false "43/43 PASS" + exit 0 a loosened ``error`` arm
    would print for the tampered copy."""

    flipped = json.loads(json.dumps(cases()))
    relabelled = next(
        case for case in flipped if case["id"] == "S12_COVERAGE_STARVATION"
    )
    relabelled["expected"]["error"] = True
    path = tmp_path / "error_flipped_cases.json"
    path.write_text(json.dumps(flipped), encoding="utf-8")

    assert stress_suite.main(["--cases", str(path)]) == 1
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 44
    assert lines[-1] == "BF-02 stress: 42/43 PASS"
    (line,) = [line for line in lines if line.startswith("S12_")]
    assert line.endswith("DIVERGENCE")
    assert "error: true" in line
    assert "SELECT debt" in line


def test_a_malformed_case_is_answered_per_case_not_with_a_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The refusal arm's width, at the file level. A case whose ``target_mode``
    is not a word of the vocabulary is a caller's data: :func:`run_input`'s
    arm has to answer it as a ``REFUSED`` record — with its own ``CaseRefusal``
    — so the CLI prints a table with one DIVERGENCE line and exits non-zero,
    rather than dying on an uncaught ``ValueError`` with no table at all."""

    malformed = json.loads(json.dumps(cases()))
    broken = next(
        case for case in malformed if case["id"] == "S12_COVERAGE_STARVATION"
    )
    broken["input"]["candidates"][0]["target_mode"] = "BOGUS"

    run = run_input(broken["input"])
    assert run.kind is CaseKind.REFUSED
    assert run.decision is None
    assert run.refusal is not None
    assert run.refusal.error_type == "ValueError"
    assert "BOGUS" in run.refusal.message
    assert not verdict_of(broken).passed

    path = tmp_path / "malformed_cases.json"
    path.write_text(json.dumps(malformed), encoding="utf-8")

    assert stress_suite.main(["--cases", str(path)]) == 1
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 44
    assert lines[-1] == "BF-02 stress: 42/43 PASS"
    (line,) = [line for line in lines if line.startswith("S12_")]
    assert line.endswith("DIVERGENCE")
    assert "REFUSED ValueError" in line


# ---------------------------------------------------------------------------
# ④ the error cases, one condition at a time
# ---------------------------------------------------------------------------


def test_every_error_case_is_refused_for_the_condition_its_description_names() -> None:
    """Six ``error: true`` cases, six different conditions, each named by the
    refusal — and the set of refused cases is exactly those six, so a case that
    became an error by accident shows up here."""

    refused: list[str] = []
    for case in cases():
        if not case["expected"]["error"]:
            continue
        refused.append(case["id"])
        run = run_input(case["input"])
        assert run.kind is CaseKind.REFUSED, case["id"]
        assert run.refusal is not None
        assert run.refusal.error_type == "PlannerInputError", case["id"]
        for fragment in REFUSAL_CONDITIONS[case["id"]]:
            assert fragment in run.refusal.message, (case["id"], fragment)
    assert refused == list(REFUSAL_CONDITIONS)
    assert set(REFUSAL_CONDITIONS) == {
        case["id"] for case in cases() if case["expected"]["error"]
    }


def test_no_other_case_is_refused() -> None:
    """The complement: the other 37 answer a decision or a status, so a refusal
    that leaked out of the boundary is visible."""

    for case in cases():
        if case["expected"]["error"]:
            continue
        assert run_input(case["input"]).kind is not CaseKind.REFUSED, case["id"]


# ---------------------------------------------------------------------------
# ③ the three registered divergences, modelled at the boundary
# ---------------------------------------------------------------------------


def test_s04_is_refused_for_the_duplicate_key_and_the_kernel_still_merges() -> None:
    """S04's shape: two *distinct* ids sharing one ``canonical_key``. The
    boundary refuses by key (not by id), and the kernel — handed the same two
    arrivals as proposals — merges them, which is the semantics this cut may not
    change (BF-02 §4's last line versus §4's merge)."""

    case = case_of("S04_DUPLICATE_CANONICAL")
    ids = [row["id"] for row in case["input"]["candidates"]]
    keys = [row["canonical_key"] for row in case["input"]["candidates"]]
    assert ids == ["d1", "d2"]
    assert set(keys) == {"same"}
    with pytest.raises(PlannerInputError) as refused:
        proposals_of(case["input"])
    assert "duplicate canonical_key 'same'" in str(refused.value)
    assert "duplicate candidate id" not in str(refused.value)

    merged = plan(
        kernel_input(
            (
                proposal("d1", canonical_key="same"),
                proposal("d2", canonical_key="same"),
            )
        )
    )
    (row,) = merged.trace.candidates
    assert row.candidate_id == "d1"
    assert row.merged_from == ("d1", "d2")
    assert merged.trace.selected_candidate_id == "d1"


def test_s42_is_refused_for_the_duplicate_id_which_is_checked_first() -> None:
    """S42's shape: one id **and** one key twice. The id is the fact its
    description names, and the reference's own ``validate_input`` checks it
    first, so the refusal has to be the id one."""

    case = case_of("S42_DUP_ID")
    ids = [row["id"] for row in case["input"]["candidates"]]
    keys = [row["canonical_key"] for row in case["input"]["candidates"]]
    assert ids == ["x", "x"]
    assert keys == ["x", "x"]
    with pytest.raises(PlannerInputError) as refused:
        proposals_of(case["input"])
    assert "duplicate candidate id 'x'" in str(refused.value)

    merged = plan(
        kernel_input(
            (
                proposal("x", canonical_key="x"),
                proposal("x", canonical_key="x"),
            )
        )
    )
    (row,) = merged.trace.candidates
    assert row.candidate_id == "x"
    assert row.merged_from == ("x", "x")


def test_s20_degrades_because_the_context_is_read_before_the_vector() -> None:
    """S20's shape: a short vector **and** an INCOMPLETE assembly. BF-02 §5
    answers ``DEGRADED`` first (the reference's own ``_precheck_context``),
    while the kernel keeps §10.1's order — so the same input handed straight to
    the kernel raises the §20 contract error, and that difference is the whole
    reason this check lives outside the kernel."""

    case = case_of("S20_MISSING_FACTOR_DEGRADE")
    (row,) = case["input"]["candidates"]
    assert "schedule_urgency" not in row["benefit"]
    assert (
        case["input"]["planning_context"]["feature_assembly_status"]
        == "INCOMPLETE"
    )
    assert degraded_reason_of(case["input"]) == "FEATURE_ASSEMBLY_INCOMPLETE"
    run = run_input(case["input"])
    assert run.kind is CaseKind.DEGRADED
    assert run.decision is None
    assert run.degraded_reason == "FEATURE_ASSEMBLY_INCOMPLETE"

    with pytest.raises(PlannerInputError) as refused:
        kernel.plan(planning_input_of(case["input"]))
    assert "schedule_urgency" in str(refused.value)
    assert "not declared" in str(refused.value)


def test_the_synthesized_row_is_what_makes_the_declared_urgency_legal() -> None:
    """Judgement 2's seam, positively: the row the adapter builds is a real
    §5.2 row whose stored urgency *is* the declared number, and the two cases
    that declare a non-zero one are answered by it."""

    row = schedule_row_of("c1", 0.75)
    assert isinstance(row, ScheduleItem)
    assert row.review_urgency == 0.75
    assert row.source_learning_watermark == "0"

    for case_id in ("S15_BLOCKING_ERROR_VS_REVIEW", "S16_LOW_ERROR_VS_REVIEW"):
        declared = [
            candidate["benefit"]["schedule_urgency"]
            for candidate in case_of(case_id)["input"]["candidates"]
            if candidate["benefit"]["schedule_urgency"]
        ]
        assert declared == [1.0], case_id
        assert run_input(case_of(case_id)["input"]).kind is CaseKind.SELECT


def test_the_undeclared_fallback_row_is_present_and_cannot_reach_a_verdict() -> None:
    """Judgement 2's placeholder, pinned both ways. S20's candidate leaves the
    name out of its vector (judgement 1), so its row cannot spell a declaration:
    it carries :data:`_UNDECLARED_ROW_URGENCY` — and that number is inert, which
    is the stronger half: §20's completeness check refuses the same vector
    identically when the row answers something else, so the placeholder is not
    a second declaration that a verdict could rest on."""

    base = planning_input_of(case_of("S20_MISSING_FACTOR_DEGRADE")["input"])
    (candidate,) = base.proposals
    assert isinstance(candidate.schedule_row, ScheduleItem)
    assert candidate.schedule_row.review_urgency == (
        stress_suite._UNDECLARED_ROW_URGENCY
    )
    assert candidate.benefit.get(kernel.BenefitFactor.SCHEDULE_URGENCY) is None

    moved = replace(
        base,
        proposals=(
            replace(candidate, schedule_row=schedule_row_of("x", 0.99)),
        ),
    )
    for planning_input in (base, moved):
        with pytest.raises(PlannerInputError) as refused:
            kernel.plan(planning_input)
        assert "schedule_urgency" in str(refused.value)
        assert "not declared" in str(refused.value)


# ---------------------------------------------------------------------------
# ④ the custom cases, one predicate at a time
# ---------------------------------------------------------------------------


def test_the_three_degraded_customs_answer_a_status_and_no_decision() -> None:
    expected = {
        "S05_AUTH_UNAVAILABLE": "FEATURE_ASSEMBLY_INCOMPLETE",
        "S06_STALE_SNAPSHOT": "SNAPSHOT_INVALID",
        "S20_MISSING_FACTOR_DEGRADE": "FEATURE_ASSEMBLY_INCOMPLETE",
    }
    for case_id, reason in expected.items():
        run = run_input(case_of(case_id)["input"])
        assert run.kind is CaseKind.DEGRADED, case_id
        assert run.decision is None, case_id
        assert run.degraded_reason == reason, case_id
        assert run.scored == (), case_id


def test_the_equal_utility_case_is_equal_on_the_raw_numbers_too() -> None:
    """S21's origin labels buy nothing. The frozen runner compares the rounded
    utilities; the raw ones are equal as well, so the rounding replica is not
    what makes the case pass (module judgement 8)."""

    run = run_input(case_of("S21_ORIGIN_NO_SCORE")["input"])
    assert len(run.scored) == 2
    assert run.scored[0][1] == run.scored[1][1]
    raw = raw_utilities("S21_ORIGIN_NO_SCORE")
    assert len(raw) == 2
    assert len(set(raw.values())) == 1


def test_the_two_monotonicity_customs_hold_on_the_raw_numbers_too() -> None:
    """S29 (higher context fit cannot lower utility) and S30 (higher
    interruption cost cannot raise utility) are strict where they can be, and
    hold unrounded as well."""

    benefit = raw_utilities("S29_BENEFIT_MONOTONIC")
    assert benefit["hi"] > benefit["lo"]
    rounded = dict(run_input(case_of("S29_BENEFIT_MONOTONIC")["input"]).scored)
    assert rounded["hi"] >= rounded["lo"]

    cost = raw_utilities("S30_COST_MONOTONIC")
    assert cost["cl"] > cost["ch"]
    rounded_cost = dict(
        run_input(case_of("S30_COST_MONOTONIC")["input"]).scored
    )
    assert rounded_cost["cl"] >= rounded_cost["ch"]


def test_the_order_case_is_deterministic_and_then_some() -> None:
    """S31: the reference asks that the *decision* survive a reversed candidate
    list; here the whole kernel result does — the stronger fact, pinned beside
    the predicate the runner reproduces (module judgement 8)."""

    case = case_of("S31_ORDER")
    forward = plan(planning_input_of(case["input"]))
    reversed_result = plan(planning_input_of(case["input"], reverse=True))
    assert reversed_result.outcome.decision == forward.outcome.decision
    assert reversed_result == forward
    run = run_input(case["input"])
    assert run.kind is CaseKind.SELECT
    assert run.selected == "debt"
    assert run_input(case["input"], reverse=True).decision == run.decision


# ---------------------------------------------------------------------------
# ⑥ the frozen reference stays read-only
# ---------------------------------------------------------------------------


def test_the_two_reference_copies_are_byte_identical_and_unimported() -> None:
    """``behavioral_baselines/golden/planner_reference_v1_1.py`` and
    ``behavioral_baselines/planner/planner_reference_v1_1.py`` are one file
    twice, and nothing under ``src/`` imports either: the replay reads the
    *cases*, and an implementation that depended on the frozen reference would
    be the thing this pin forbids."""

    left, right = REFERENCE_COPIES
    left_bytes = left.read_bytes()
    right_bytes = right.read_bytes()
    assert left_bytes == right_bytes
    assert hashlib.sha256(left_bytes).hexdigest() == (
        hashlib.sha256(right_bytes).hexdigest()
    )
    offenders: list[str] = []
    for path in sorted((REPO_ROOT / "src").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            offenders.extend(
                f"{path.name}: {name}"
                for name in names
                if "planner_reference" in name
            )
    assert offenders == []


def test_the_replay_is_not_on_the_production_face() -> None:
    """Judgement 10: the package does not export the suite, and no ``src/``
    module imports it — the kernel it runs is the one every consumer runs."""

    import elc.planner as package

    assert "stress_suite" not in set(package.__all__)
    for name, relative in (("__init__", "src/elc/planner/__init__.py"),):
        tree = ast.parse(source_text(relative))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            assert not any("stress_suite" in item for item in names), (
                name,
                names,
            )
    importers: list[str] = []
    for path in sorted((REPO_ROOT / "src").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            if any("stress_suite" in item for item in names):
                importers.append(f"{path.name}: {names}")
    assert importers == []


# ---------------------------------------------------------------------------
# ⑤ the module's own registered judgements
# ---------------------------------------------------------------------------


def _declared_judgements(relative: str) -> tuple[str, ...]:
    """The ``**Declared judgements.**`` section, one entry per numbered line.

    The module claims "each entry … names the condition that re-opens it", and
    this reads the claim entry by entry — a whole-file "``Revisit:`` appears
    somewhere" check could not fail.
    """

    source = source_text(relative)
    start = source.index("**Declared judgements.**")
    end = source.index("**Versioning.**")
    entries: list[str] = []
    current: list[str] = []
    for line in source[start:end].splitlines():
        if _NUMBERED.match(line.strip()):
            if current:
                entries.append("\n".join(current))
            current = [line]
        elif current:
            current.append(line)
    if current:
        entries.append("\n".join(current))
    return tuple(entries)


#: One numbered judgement entry ("7. **…**", ten and up included).
_NUMBERED = re.compile(r"^\d+\. ")


def test_the_suite_registers_its_readings_with_a_revisit_each() -> None:
    """The module's own claim ("each entry … names the condition that re-opens
    it"), read one entry at a time, with the floor this cut declares."""

    judgements = _declared_judgements(SUITE_MODULE)
    assert len(judgements) >= 10
    for judgement in judgements:
        assert "Revisit:" in judgement, judgement[:120]


def test_the_suites_own_version_stamp_is_pinned() -> None:
    """The versioning paragraph's claim, pinned the way its four siblings'
    stamps are (``fa1`` / ``pk1`` / ``pl1`` / ``sh1``): the module says the
    stamp moves with its readings, so its present value is asserted rather
    than left to be inherited by a reader's eyes alone."""

    assert STRESS_SUITE_MODEL_VERSION == "bf02-suite-1"


def test_the_not_scheduled_gap_is_not_exercised_by_this_suite() -> None:
    """Judgement 9's reading, both halves. Every candidate in the frozen suite
    gets a synthesized §5.2 row, so none of them reaches the kernel's
    no-row gap (its judgement 13) — and the only two non-zero declarations are
    the two cases that need a row to answer a number at all."""

    non_zero = [
        (case["id"], candidate["id"])
        for case in cases()
        for candidate in case["input"]["candidates"]
        if candidate["benefit"].get("schedule_urgency", 0.0) != 0.0
    ]
    assert non_zero == [
        ("S15_BLOCKING_ERROR_VS_REVIEW", "z_review"),
        ("S16_LOW_ERROR_VS_REVIEW", "z_review"),
    ]
    missing = [
        (case["id"], candidate["id"])
        for case in cases()
        for candidate in case["input"]["candidates"]
        if "schedule_urgency" not in candidate["benefit"]
    ]
    assert missing == [("S20_MISSING_FACTOR_DEGRADE", "x")]
    # Judgement 9's own count, machine-read: the cases every one of whose
    # candidates *declares* ``0.0`` — the rows that keep them from becoming the
    # gap a row-less adaptation would have made of them. The explicit
    # declaration is the claim, so S20's missing name is not one of them even
    # though the fallback placeholder is also 0.0.
    all_zero = [
        case["id"]
        for case in cases()
        if all(
            candidate["benefit"].get("schedule_urgency") == 0.0
            for candidate in case["input"]["candidates"]
        )
    ]
    assert len(all_zero) == 40
    for case in cases():
        if case["expected"]["error"]:
            continue  # the boundary's refusals have their own test
        for row in proposals_of(case["input"]):
            assert isinstance(row.schedule_row, ScheduleItem), case["id"]
            declared = row.benefit.get(kernel.BenefitFactor.SCHEDULE_URGENCY)
            if declared is not None:
                assert row.schedule_row.review_urgency == declared, case["id"]
    prose = " ".join(source_text(SUITE_MODULE).split())
    assert "NOT_SCHEDULED" in prose
    assert "judgement 13" in prose
    assert "the forty cases" in prose


def test_the_boundary_block_registers_both_divergences_with_a_revisit() -> None:
    """The registration the task's four checks ask for lives in the module's
    own boundary block, one bullet per divergence, each naming the condition
    that re-opens it — so a reader meets the three settlements (S04/S42 at the
    boundary, S20 before the kernel) before the numbered judgements."""

    source = source_text(SUITE_MODULE)
    start = source.index("**The adapter boundary")
    end = source.index("**Declared judgements.**")
    block = source[start:end]
    for case_id in ("S04", "S42", "S20"):
        assert case_id in block, case_id
    assert block.count("Revisit:") == 2
