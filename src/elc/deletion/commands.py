"""Deletion domain command face (the write protocol).

One write: :meth:`DeletionCommands.execute`. A deletion is not a settable
state — a caller asks for a *scope* to be removed and the domain decides what
that scope means (which rows, in which order, and what has to be rebuilt
afterwards), which is why the request carries a scope word plus the keys that
scope needs rather than a list of rows to remove.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from elc.deletion.types import (
    DeletionOutcome,
    DeletionRequest,
)
from elc.platform.types import Result

__all__ = ["DeletionCommands"]


@runtime_checkable
class DeletionCommands(Protocol):
    """The removal face (BF-05 §18–§23)."""

    def execute(self, request: DeletionRequest) -> Result[DeletionOutcome]:
        """Run one deletion request, then rebuild what still has a source.

        Returns the durable execution (what was removed, what was
        tombstoned, what was cancelled) *and* the rebuild attempts it drove.
        A rebuild that fails is reported in the outcome rather than raised:
        §18 lists the rebuild among deletion's semantics, so its failure is a
        fact the caller must see — never a silent partial deletion.
        """
        ...
