"""AST-based SQL write-target scan for the architecture pins (P3-0 review
F3, DEC-…eaaa5a1d.58).

Why AST instead of a substring scan: a plain ``"INSERT INTO decision_cycle"
in text`` check is defeatable by an ordinary multi-line SQL literal
(``"INSERT INTO " "decision_cycle …"``), by ``"INSERT INTO " + table``, or
by an f-string. This module folds every string expression a module builds
from literals — adjacent literal concatenation and ``+`` of literals — and
only then looks for write verbs, so the P3-1A write-face pins cannot be
bypassed by formatting.

Honest limit: SQL assembled from runtime values (f-strings, ``%``,
``str.join``) is NOT foldable and is invisible here — the repo bans
identifier assembly outright (fixed-literal SQL + bound parameters), so
such code is a different violation, caught by review rather than by this
scan.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

__all__ = [
    "WRITE_STATEMENT_RE",
    "folded_strings",
    "write_targets",
    "write_targets_from_source",
]

#: Insert/update/delete statement heads, whitespace-normalized.
WRITE_STATEMENT_RE = re.compile(
    r"\b(?:insert\s+into|update|delete\s+from)\s+([A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE,
)


def _as_text(node: ast.AST) -> str | None:
    """Fold one string expression: literal, adjacent concatenation (already
    folded by the parser into a single Constant), or ``+`` of foldable
    operands."""

    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _as_text(node.left)
        right = _as_text(node.right)
        if left is not None and right is not None:
            return left + right
    return None


def folded_strings(source: str) -> list[str]:
    """Every string expression in the module, folded where foldable."""

    tree = ast.parse(source)
    found: list[str] = []
    for node in ast.walk(tree):
        text = _as_text(node)
        if text is not None:
            found.append(text)
    return found


def write_targets_from_source(source: str) -> set[str]:
    """The set of table names this source writes to (lower-cased)."""

    targets: set[str] = set()
    for text in folded_strings(source):
        for match in WRITE_STATEMENT_RE.finditer(text):
            targets.add(match.group(1).lower())
    return targets


def write_targets(path: Path) -> set[str]:
    """The set of table names the module at ``path`` writes to."""

    return write_targets_from_source(path.read_text(encoding="utf-8"))
