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

Two readers share the fold, and they answer different questions:

- :func:`write_targets` — *which tables* a module writes to. The match is
  anywhere in a folded literal, because a table name is what it asks for and
  a repeated mention costs nothing.
- :func:`write_statements` — *which statement class* (verb) the module
  applies to each table. The match is anchored at the start of the folded
  literal, because here prose matters: elc/deletion/store.py's own docstring
  says "the ordinary create/update verbs stay with …", and an unanchored
  ``update\\s+([A-Za-z_]\\w*)`` reads that sentence as an ``UPDATE verbs``
  statement. A literal that *begins* with a write head is a statement; a
  sentence that mentions one is not. The two readers are held to the same
  table set by a pin in tests/deletion/test_deletion_surfaces.py.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

__all__ = [
    "STATEMENT_HEAD_RE",
    "WRITE_STATEMENT_RE",
    "folded_strings",
    "write_statements",
    "write_statements_from_source",
    "write_targets",
    "write_targets_from_source",
]

#: Insert/update/delete statement heads, whitespace-normalized.
WRITE_STATEMENT_RE = re.compile(
    r"\b(?:insert\s+into|update|delete\s+from)\s+([A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE,
)

#: A statement head that opens its folded literal, with the verb captured.
#: See the module docstring for why the anchor is load-bearing.
STATEMENT_HEAD_RE = re.compile(
    r"^\s*(insert\s+into|update|delete\s+from)\s+([A-Za-z_][A-Za-z0-9_]*)",
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


def _statement_literals(tree: ast.AST) -> list[str]:
    """The foldable literals that are not part of a larger foldable one.

    A statement split with ``+`` of literals is *one* statement, and
    :func:`folded_strings` yields every piece of it — the whole and each
    operand. Counting verbs over that would count a two-piece statement twice,
    so the outermost fold wins here. (``write_targets`` keeps the inclusive
    walk on purpose: it wants the set of tables, where a sub-expression is
    harmless.)
    """

    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    found: list[str] = []
    for node in ast.walk(tree):
        text = _as_text(node)
        if text is None:
            continue
        parent = parents.get(node)
        if parent is not None and _as_text(parent) is not None:
            continue
        found.append(text)
    return found


def write_statements_from_source(source: str) -> dict[str, tuple[str, ...]]:
    """Table (lower-cased) → the write verbs this source applies to it.

    Verbs are normalized to ``INSERT`` / ``UPDATE`` / ``DELETE``, sorted, and
    **duplicates are preserved**: ``("DELETE", "UPDATE")`` is one delete and
    one update, ``("DELETE", "UPDATE", "UPDATE")`` is two updates — which is
    what a pin needs in order to say "exactly one update, and it is this one
    shape". A table no statement writes is absent rather than empty, so a
    caller reads it with ``.get(table)``.
    """

    statements: dict[str, list[str]] = {}
    for text in _statement_literals(ast.parse(source)):
        match = STATEMENT_HEAD_RE.match(text)
        if match is None:
            continue
        verb = match.group(1).upper().split()[0]
        table = match.group(2).lower()
        statements.setdefault(table, []).append(verb)
    return {table: tuple(sorted(verbs)) for table, verbs in statements.items()}


def write_statements(path: Path) -> dict[str, tuple[str, ...]]:
    """The statement classes the module at ``path`` carries, by table."""

    return write_statements_from_source(path.read_text(encoding="utf-8"))
