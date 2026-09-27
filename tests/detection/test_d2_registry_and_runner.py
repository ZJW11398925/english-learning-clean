"""D-2 — the detection harness's unit face: registry and runner.

The runner judgment, pinned arm by arm (the R6 criteria): a NEGATIVE row
must not match, a FALSE_POSITIVE_BOUNDARY row must not match either (the
boundary word is a semantic marker, not a different judgment), and a
POSITIVE_ERROR row must match **with the row's own declared
source_error_type** — a typed hit or nothing.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from elc.detection import (
    DetectorRegistry,
    run_fixture,
    run_fixtures,
)
from tests.conftest import REPO_ROOT
from tests.detection.support import (
    SyntheticFixture,
    always_match,
    make_fixture,
    match_when,
    never_match,
)

# ---------------------------------------------------------------------------
# the runner judgment — the eight arms
# ---------------------------------------------------------------------------


def test_a_negative_row_that_matches_fails() -> None:
    outcome = run_fixture(
        always_match("SOME_TYPE"),
        make_fixture(0, "NEGATIVE", "Anyway, fine."),
    )
    assert outcome.matched is True
    assert outcome.matched_error_type == "SOME_TYPE"
    assert outcome.passed is False
    assert (outcome.ordinal, outcome.kind, outcome.expected) == (
        0,
        "NEGATIVE",
        "NO_MATCH",
    )


def test_a_negative_row_that_does_not_match_passes() -> None:
    outcome = run_fixture(
        never_match,
        make_fixture(1, "NEGATIVE", "Anyway, fine."),
    )
    assert outcome.matched is False
    assert outcome.matched_error_type is None
    assert outcome.passed is True


def test_a_boundary_row_that_matches_fails() -> None:
    outcome = run_fixture(
        always_match("SOME_TYPE"),
        make_fixture(2, "FALSE_POSITIVE_BOUNDARY", "any way to fix this?"),
    )
    assert outcome.matched is True
    assert outcome.passed is False


def test_a_boundary_row_that_does_not_match_passes() -> None:
    outcome = run_fixture(
        never_match,
        make_fixture(3, "FALSE_POSITIVE_BOUNDARY", "any way to fix this?"),
    )
    assert outcome.matched is False
    assert outcome.passed is True


def test_a_positive_row_that_does_not_match_fails() -> None:
    outcome = run_fixture(
        never_match,
        make_fixture(
            4, "POSITIVE_ERROR", "Any way, as I was saying.", "SPLIT_SPELLING"
        ),
    )
    assert outcome.matched is False
    assert outcome.matched_error_type is None
    assert outcome.passed is False


def test_a_positive_row_matched_with_the_declared_type_passes() -> None:
    outcome = run_fixture(
        match_when("Any way,", "SPLIT_SPELLING"),
        make_fixture(
            5, "POSITIVE_ERROR", "Any way, as I was saying.", "SPLIT_SPELLING"
        ),
    )
    assert outcome.matched is True
    assert outcome.matched_error_type == "SPLIT_SPELLING"
    assert outcome.passed is True


def test_a_positive_row_matched_with_the_wrong_type_fails() -> None:
    """A hit alone is not a pass: the hit must name the row's own declared
    source_error_type (R6)."""

    outcome = run_fixture(
        always_match("SOME_OTHER_TYPE"),
        make_fixture(
            6, "POSITIVE_ERROR", "Any way, as I was saying.", "SPLIT_SPELLING"
        ),
    )
    assert outcome.matched is True
    assert outcome.matched_error_type == "SOME_OTHER_TYPE"
    assert outcome.passed is False


def test_run_fixtures_aggregates_and_any_single_failure_blocks_the_pass() -> None:
    """One verified row and one violated row: the aggregate is False, with
    every row's outcome kept."""

    fixtures = (
        make_fixture(
            0, "POSITIVE_ERROR", "Any way, as I was saying.", "SPLIT_SPELLING"
        ),
        make_fixture(1, "NEGATIVE", "Anyway, fine."),
    )
    good = run_fixtures(
        match_when("Any way,", "SPLIT_SPELLING"), fixtures, entity_id="res-x"
    )
    assert good.entity_id == "res-x"
    assert good.fixture_count == 2
    assert len(good.outcomes) == 2
    assert good.all_passed is True

    sloppy = run_fixtures(
        match_when("way", "SPLIT_SPELLING"), fixtures, entity_id="res-x"
    )
    assert sloppy.outcomes[0].passed is True
    assert sloppy.outcomes[1].passed is False
    assert sloppy.all_passed is False


# ---------------------------------------------------------------------------
# the registry
# ---------------------------------------------------------------------------


def test_registry_roundtrip_sorted_views_and_empty_rule_ordinals() -> None:
    registry = DetectorRegistry()
    registry.register("res-b", (), never_match)
    registry.register("res-a", (0, 2), always_match("X"))
    assert registry.resolve("res-a") is not None
    assert registry.resolve("res-b") is not None
    assert registry.resolve("missing") is None
    assert registry.known_targets() == ("res-a", "res-b")
    entries = registry.entries()
    assert [entry.entity_id for entry in entries] == ["res-a", "res-b"]
    assert entries[0].rule_ordinals == (0, 2)
    # An empty rule_ordinals is a legal, honest claim ("this matcher
    # corresponds to no declared rule prose"); its validity against the
    # entity's rules is the build's business, not the registry's.
    assert entries[1].rule_ordinals == ()
    assert entries[1].matcher is not None


def test_duplicate_registration_is_refused_and_replaces_nothing() -> None:
    registry = DetectorRegistry()
    registry.register("res-a", (), never_match)
    with pytest.raises(ValueError, match="res-a"):
        registry.register("res-a", (0,), always_match("X"))
    # The refusal is not a replacement: the original entry stands.
    entries = registry.entries()
    assert len(entries) == 1
    assert entries[0].rule_ordinals == ()


def test_the_global_registry_ships_empty() -> None:
    """V1 registers no matcher: importing the package is side-effect
    free, so a fresh interpreter sees the module-level default empty.
    (Read in a fresh interpreter: an in-process CLI assembly — D-3's
    ``main`` — legitimately populates the object afterwards, and that is
    an assembly act, not an import effect.)"""

    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from elc.detection import GLOBAL_REGISTRY;"
            "print(GLOBAL_REGISTRY.known_targets())",
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "()"


def test_an_unknown_fixture_kind_is_refused_not_scored() -> None:
    """A fourth kind would be a source-vocabulary drift (the build refuses
    it upstream); the runner fails closed rather than scoring it."""

    with pytest.raises(ValueError, match="unknown fixture kind"):
        run_fixture(
            never_match,
            SyntheticFixture(0, "SOME_FOURTH_KIND", "text", "NO_MATCH"),
        )
