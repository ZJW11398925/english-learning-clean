"""D-3 — the pilot detector set: twelve targets, verified executable.

Pinned here: every pilot matcher passes its own real fixture set (the
run_fixtures judgment, against the authoring source), the CLI artifact
carries exactly the pilot EV set (12 EV / 34 EDITOR / 54 AUTHOR), the
two-directional face (the same tree builds EDITOR-baseline by default
and EV under the pilot registry), the pilot registration's completeness
(PILOT_ENTITIES ≡ the registered set; a second registration is refused;
GLOBAL_REGISTRY still ships empty at import), the non-pilot candidates
stay at their baseline level, the anti-hardcoding scan (no fixture
POSITIVE sentence opening may appear in the matcher sources), and the
generalization probes (same-pattern new sentences are judged — the
matchers read rules, not fixture text).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from elc.content.build import (
    CONTENT_SRC_DIR,
    CURRICULUM_DIR,
    build_content_db,
    load_source,
)
from elc.detection import DetectorRegistry, run_fixtures
from elc.detection.pilot import PILOT_ENTITIES, register_pilot
from tests.conftest import REPO_ROOT, SRC_ROOT
from tests.detection.support import provenance_map

_PATTERN_SOURCES = (
    SRC_ROOT / "detection" / "patterns.py",
    SRC_ROOT / "detection" / "pilot.py",
)

#: Non-pilot candidates from the same R4∧EDITOR pool, sampled for the
#: original-level pin (a pilot build must not move them).
_NON_PILOT_CANDIDATES = (
    "res-discourse-on-another-note",
    "res-pragmatic-right",
    "res-softener-kind-of",
)


@pytest.fixture(scope="module")
def source_documents() -> dict[str, Any]:
    """The authoring source's evidence documents, by entity id."""

    source = load_source(CONTENT_SRC_DIR, CURRICULUM_DIR)
    return {document.entity_id: document for document in source.evidence}


def _pilot_registry() -> DetectorRegistry:
    registry = DetectorRegistry()
    register_pilot(registry)
    return registry


# ---------------------------------------------------------------------------
# group 1 — every pilot matcher passes its own real fixture set
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("entity_id", PILOT_ENTITIES)
def test_every_pilot_matcher_passes_its_own_fixture_set(
    source_documents: dict[str, Any], entity_id: str
) -> None:
    entry = next(
        entry
        for entry in _pilot_registry().entries()
        if entry.entity_id == entity_id
    )
    outcome = run_fixtures(
        entry.matcher,
        source_documents[entity_id].detection_fixtures,
        entity_id=entity_id,
    )
    assert outcome.fixture_count > 0
    failures = [
        (row.ordinal, row.kind, row.text, row.matched_error_type)
        for row in outcome.outcomes
        if not row.passed
    ]
    assert outcome.all_passed, failures


# ---------------------------------------------------------------------------
# group 2 — the CLI artifact carries exactly the pilot EV set
# ---------------------------------------------------------------------------


def test_the_cli_artifact_carries_exactly_the_pilot_ev_set(
    tmp_path: Path,
) -> None:
    out = tmp_path / "cli-content.db"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-m", "elc.content.build", "--out", str(out)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env=env,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    levels = list(provenance_map(out).values())
    ev = sorted(
        entity
        for entity, level in provenance_map(out).items()
        if level == "EXECUTABLY_VERIFIED"
    )
    assert ev == sorted(PILOT_ENTITIES)
    assert levels.count("EXECUTABLY_VERIFIED") == 12
    assert levels.count("EDITOR_REVIEWED") == 34
    assert levels.count("AUTHOR_DECLARED") == 54
    assert levels.count("EMPIRICALLY_CALIBRATED") == 0


# ---------------------------------------------------------------------------
# group 3 — the two-directional face on the same tree
# ---------------------------------------------------------------------------


def test_the_same_tree_builds_editor_baseline_by_default_and_ev_under_the_pilot(
    tmp_path: Path,
) -> None:
    baseline_db = tmp_path / "baseline.db"
    build_content_db(baseline_db)
    baseline = provenance_map(baseline_db)
    assert "EXECUTABLY_VERIFIED" not in baseline.values()
    for entity in PILOT_ENTITIES:
        assert baseline[entity] == "EDITOR_REVIEWED", entity

    promoted_db = tmp_path / "promoted.db"
    build_content_db(promoted_db, detector_registry=_pilot_registry())
    promoted = provenance_map(promoted_db)
    for entity in PILOT_ENTITIES:
        assert promoted[entity] == "EXECUTABLY_VERIFIED", entity
    others = {
        entity: level
        for entity, level in promoted.items()
        if entity not in PILOT_ENTITIES
    }
    assert others == {
        entity: level
        for entity, level in baseline.items()
        if entity not in PILOT_ENTITIES
    }


# ---------------------------------------------------------------------------
# group 4 — the default answer stays registry-free
# ---------------------------------------------------------------------------


def test_importing_the_package_and_the_pilot_registers_nothing() -> None:
    """The default answer stays registry-free: neither importing the
    detection package nor the pilot module registers a matcher — the
    pilot set exists only where an entry point calls
    :func:`register_pilot` (the CLI's ``main``, D-3). Read in a fresh
    interpreter, so an earlier in-process CLI assembly cannot masquerade
    as an import effect; the default build itself stays pinned at zero
    EV by the D-2 byte-identity test."""

    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "import elc.detection, elc.detection.pilot;"
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


# ---------------------------------------------------------------------------
# group 5 — non-pilot candidates stay at their baseline level
# ---------------------------------------------------------------------------


def test_non_pilot_candidates_keep_their_baseline_level(tmp_path: Path) -> None:
    baseline_db = tmp_path / "baseline.db"
    build_content_db(baseline_db)
    baseline = provenance_map(baseline_db)

    promoted_db = tmp_path / "promoted.db"
    build_content_db(promoted_db, detector_registry=_pilot_registry())
    promoted = provenance_map(promoted_db)

    for entity in _NON_PILOT_CANDIDATES:
        assert entity in baseline
        assert promoted[entity] == baseline[entity]
        assert promoted[entity] != "EXECUTABLY_VERIFIED"


# ---------------------------------------------------------------------------
# group 6 — the anti-hardcoding scan
# ---------------------------------------------------------------------------


def test_no_fixture_sentence_opening_appears_in_the_matcher_sources(
    source_documents: dict[str, Any],
) -> None:
    """A matcher that echoed fixture sentences would contain them; the
    scan takes each POSITIVE fixture's first six words and refuses the
    sequence in patterns.py or pilot.py. Both sides are read as word
    tokens (punctuation dropped), so a quoted sentence cannot hide its
    commas."""

    corpus = " ".join(
        re.findall(
            r"[a-z']+",
            "\n".join(
                path.read_text(encoding="utf-8") for path in _PATTERN_SOURCES
            ).lower(),
        )
    )
    for entity in PILOT_ENTITIES:
        for row in source_documents[entity].detection_fixtures:
            if row.kind != "POSITIVE_ERROR":
                continue
            probe = " ".join(re.findall(r"[a-z']+", row.text.lower())[:6])
            assert len(probe.split()) == 6
            assert probe not in corpus, (entity, row.ordinal, probe)


# ---------------------------------------------------------------------------
# group 7 — generalization probes: same pattern, new words
# ---------------------------------------------------------------------------


def test_same_pattern_new_sentences_are_judged_by_rule_not_by_text() -> None:
    from elc.detection.pilot import (
        detect_anyway,
        detect_got_it,
        detect_that_makes_sense,
    )

    # got-it: the receipt slip with a fresh promise clause; the correct
    # past receipt with the same clause stays silent.
    assert (
        detect_got_it("Get it, I will call you tomorrow.").error_type
        == "FORM_SLIP"
    )
    assert detect_got_it("Got it, I will call you tomorrow.") is None

    # anyway: the split spelling fronted on a new matter; the noun-phrase
    # question refuses.
    assert (
        detect_anyway("Any way, the agenda moves to Friday.").error_type
        == "SPLIT_SPELLING"
    )
    assert detect_anyway("Is there any way to help us move?") is None

    # that-makes-sense: the bare make on a fresh frame; the -s form and
    # the negative frame stay silent.
    assert (
        detect_that_makes_sense(
            "That make sense to me, thanks for explaining."
        ).error_type
        == "SUBJECT_VERB_AGREEMENT"
    )
    assert detect_that_makes_sense("That makes sense to me, thanks.") is None
    assert (
        detect_that_makes_sense("That doesn't make sense to me at all.")
        is None
    )


# ---------------------------------------------------------------------------
# the pilot registration's completeness
# ---------------------------------------------------------------------------


def test_register_pilot_registers_the_pilot_roster_and_refuses_a_second() -> None:
    registry = _pilot_registry()
    assert registry.known_targets() == tuple(sorted(PILOT_ENTITIES))
    ordinals = {
        entry.entity_id: entry.rule_ordinals for entry in registry.entries()
    }
    assert all(ordinals[entity] for entity in PILOT_ENTITIES)
    with pytest.raises(ValueError):
        register_pilot(registry)
