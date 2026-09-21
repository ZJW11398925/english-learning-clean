"""Shared fixtures for the P5-0 content.db tests.

The fixture corpus under test is the repository's real authoring source
(`content_src/` + `curriculum/`) built by `elc.content.build`; tests never
hand-write a content.db, because the artifact's whole point is that it is
generated. `built_content_db` builds once per session into a pytest temp
directory (the artifact is gitignored and never committed).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterator

import pytest

from elc.content.build import CONTENT_SRC_DIR, CURRICULUM_DIR, build_content_db
from elc.content.store import ContentStore
from tests.conftest import REPO_ROOT

DOCS_ROOT = REPO_ROOT / "docs"

__all__ = [
    "CONTENT_SRC_DIR",
    "CURRICULUM_DIR",
    "DOCS_ROOT",
    "canonical_blocks",
    "canonical_lines",
]


@pytest.fixture(scope="session")
def built_content_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The repository's content.db, built once for the whole session."""

    output = tmp_path_factory.mktemp("p5-0-content") / "content.db"
    build_content_db(output)
    return output


@pytest.fixture()
def store(built_content_db: Path) -> Iterator[ContentStore]:
    opened = ContentStore(built_content_db)
    yield opened
    opened.close()


# ---------------------------------------------------------------------------
# Canonical-document readers: pins extract the word lists from docs/ itself
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"^```")


def canonical_blocks(doc: str, heading: str) -> list[tuple[str, ...]]:
    """Every fenced block after `heading`, as (line, …) tuples.

    The canonical documents are the authority these tests pin against, so the
    word lists are extracted from the document text at test time rather than
    from a second hand-typed copy. The section ends at the next heading of the
    same or higher level (the heading's own level decides).
    """

    lines = (DOCS_ROOT / doc).read_text(encoding="utf-8").splitlines()
    level = len(heading) - len(heading.lstrip("#"))
    start = None
    for index, line in enumerate(lines):
        if line.strip() == heading:
            start = index + 1
            break
    assert start is not None, f"heading {heading!r} not found in {doc}"
    blocks: list[tuple[str, ...]] = []
    index = start
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if stripped.startswith("#"):
            head_level = len(stripped) - len(stripped.lstrip("#"))
            if head_level <= level and stripped[:head_level + 1].endswith(" "):
                break
        if _FENCE_RE.match(line):
            body: list[str] = []
            index += 1
            while index < len(lines) and not _FENCE_RE.match(lines[index]):
                if lines[index].strip():
                    body.append(lines[index].strip())
                index += 1
            if body:
                blocks.append(tuple(body))
        index += 1
    return blocks


def canonical_lines(doc: str, heading: str, block: int = 0) -> tuple[str, ...]:
    """The `block`-th fenced block after `heading` (0-based)."""

    blocks = canonical_blocks(doc, heading)
    assert len(blocks) > block, (
        f"{doc} {heading!r}: block {block} missing (found {len(blocks)})"
    )
    return blocks[block]
