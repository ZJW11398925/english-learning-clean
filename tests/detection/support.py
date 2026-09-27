"""Non-test helpers for the D-2 detection tests.

The tests/host/support.py precedent: a module pytest does not collect,
holding the fixtures and stubs the D-2 test modules share. This module MAY
import elc.content (the import pin is on ``elc.detection``, not on tests).
"""

from __future__ import annotations

import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from elc.content.build import CONTENT_SRC_DIR, CURRICULUM_DIR
from elc.content.types import DETECTION_FIXTURE_EXPECTED_BY_KIND
from elc.detection import DetectionMatch, Matcher

#: The entity the build-seam tests register against (a real, documented R4
#: resource whose five fixtures the stub below passes by construction).
ANYWAY_ENTITY = "res-discourse-anyway"

#: The stub's trigger: the split-spelling production ("Any way, " fronted
#: with a comma) — the POSITIVE row's opening, and a substring of no
#: NEGATIVE or FALSE_POSITIVE_BOUNDARY row of that entity (those read
#: "Anyway," / "anyway." / "Anyhow," / "any way to").
ANYWAY_NEEDLE = "Any way, "


@dataclass(frozen=True)
class SyntheticFixture:
    """A ``DetectionFixture`` stand-in for the runner tests.

    The same five fields as the build's ``DetectionFixtureRow``, declared
    locally so the runner judgment is exercisable without a build import.
    """

    ordinal: int
    kind: str
    text: str
    expected: str
    source_error_type: str | None = None


def make_fixture(
    ordinal: int,
    kind: str,
    text: str,
    source_error_type: str | None = None,
) -> SyntheticFixture:
    """One synthetic row with the declared kind→expected pairing applied."""

    return SyntheticFixture(
        ordinal=ordinal,
        kind=kind,
        text=text,
        expected=DETECTION_FIXTURE_EXPECTED_BY_KIND[kind],
        source_error_type=source_error_type,
    )


def never_match(text: str) -> DetectionMatch | None:
    """The honest no-op detector: nothing is ever an error."""

    return None


def always_match(error_type: str) -> Matcher:
    """A detector that answers one fixed error_type for every text."""

    def matcher(text: str) -> DetectionMatch | None:
        return DetectionMatch(error_type)

    return matcher


def match_when(needle: str, error_type: str) -> Matcher:
    """A detector that fires with ``error_type`` on one substring."""

    def matcher(text: str) -> DetectionMatch | None:
        if needle in text:
            return DetectionMatch(error_type)
        return None

    return matcher


def anyway_stub(text: str) -> DetectionMatch | None:
    """A hand stub for res-discourse-anyway's own five fixtures: it matches
    only the split-spelling production (needle above) with that row's
    declared error_type, and nothing else."""

    if ANYWAY_NEEDLE in text:
        return DetectionMatch("SPLIT_SPELLING")
    return None


def copy_source_trees(tmp_path: Path) -> tuple[Path, Path]:
    """A tmp copy of both authoring trees (the canonical tree is never
    edited); returns (content_src, curriculum)."""

    content_src = tmp_path / "content_src"
    curriculum = tmp_path / "curriculum"
    shutil.copytree(CONTENT_SRC_DIR, content_src)
    shutil.copytree(CURRICULUM_DIR, curriculum)
    return content_src, curriculum


def provenance_map(artifact: Path) -> dict[str, str]:
    """The artifact's content_provenance rows, entity → level."""

    conn = sqlite3.connect(str(artifact))
    try:
        rows = conn.execute(
            "SELECT entity_id, provenance_level FROM content_provenance"
        ).fetchall()
    finally:
        conn.close()
    return {str(entity): str(level) for entity, level in rows}
