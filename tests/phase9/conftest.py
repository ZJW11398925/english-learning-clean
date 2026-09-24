"""Phase 9 fixtures — the P8-0 world and the P8-4 world, by name.

``db`` / ``fence`` / ``cycle`` / ``second_cycle`` / ``planner_store`` are
tests.phase8.conftest's fixtures, re-exported here so this package's modules
can ask for them directly (the phase-4 precedent, which imports phase 3's
builders; a phase's *fixtures* are its world, and copying four line-for-line
fixtures would only give the two copies a chance to drift). The builders the
tests use (proposal / supply_of / request_of / failed_outcome / world / …)
are imported as plain functions in the modules that need them, the same way.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.phase8.conftest import (  # noqa: F401  (fixtures, re-exported)
    cycle,
    db,
    fence,
    other_turn,
    planner_store,
    second_cycle,
)
from tests.phase8.p8_4_world import World, build_content, world

__all__ = [
    "content",
    "cycle",
    "db",
    "fence",
    "other_turn",
    "p8world",
    "planner_store",
    "second_cycle",
]


@pytest.fixture()
def content(tmp_path: Path) -> Path:
    """The built content.db both the curriculum face and the provider read."""

    return build_content(tmp_path / "content.db")


@pytest.fixture()
def p8world(db, fence, content: Path) -> World:
    """The P8-4 world: every authority one ordinary turn's leg reads."""

    return world(db, fence, content)
