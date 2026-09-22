"""Deletion domain query face (the §24 read protocol).

Four reads, and they are the whole way anything outside this package learns
what happened to deleted data:

- :meth:`DeletionQueries.list_tombstones` — the ledger itself, optionally
  narrowed to one scope;
- :meth:`DeletionQueries.is_tombstoned` — SEC-024's question about one entity;
- :meth:`DeletionQueries.filter_tombstoned` — SEC-024's question about a batch
  of incoming records (the import guard; benchmark case S49);
- :meth:`DeletionQueries.plan_external_delete` — §25/§26's judgement about
  data that has already left the application (benchmark cases S55–S57).

The first three answer from durable state; the fourth is pure and takes the
disclosure's shape as an argument, because the app can hold no durable record
of a transmission it never made.
"""

from __future__ import annotations

from typing import Mapping, Protocol, Sequence, runtime_checkable

from elc.deletion.types import (
    DeletionScope,
    ExternalDeletionPlan,
    ExternalDisclosure,
    TombstoneRecord,
)
from elc.platform.types import Result

__all__ = ["DeletionQueries"]


@runtime_checkable
class DeletionQueries(Protocol):
    """Tombstone reads and the two §24 predicates."""

    def list_tombstones(
        self, scope: DeletionScope | None = None
    ) -> Result[tuple[TombstoneRecord, ...]]:
        """The §24 ledger, newest-value-free: identities, kinds and scopes."""
        ...

    def is_tombstoned(self, *, entity_kind: str, entity_id: str) -> Result[bool]:
        """Whether this entity is in the ledger (SEC-024's predicate).

        The id is hashed and looked up, never echoed: the ledger answers
        questions about an id it does not hold (§24's "opaque identity").
        """
        ...

    def filter_tombstoned(
        self,
        records: Sequence[Mapping[str, object]],
        *,
        entity_kind: str,
        id_field: str = "id",
    ) -> Result[tuple[Mapping[str, object], ...]]:
        """Drop every incoming record the ledger already knows about.

        §24's "tombstone wins": a stale backup cannot silently resurrect a
        deleted entity. V1 ships no import path, so this guard has no
        production caller yet — it exists so the semantics are executable and
        pinned now instead of described for later.
        """
        ...

    def plan_external_delete(
        self, disclosure: ExternalDisclosure
    ) -> Result[ExternalDeletionPlan]:
        """§25/§26's judgement; never a remote call."""
        ...
