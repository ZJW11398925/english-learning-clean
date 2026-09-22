"""BF-05 deletion — the pure derivations and the two executable predicates.

No SQL, no connection and no clock live here (the elc/scheduler/spacing.py
precedent: policy is pure, the durable layer stores what it is handed):

- the **tombstone identity** — §24 asks for a "opaque entity identity/hash"
  and pins no function, so this module declares one and nothing else in the
  package may derive it a second way;
- the **tombstone predicate and the import guard** — §24's "Import stale
  backup 时：tombstone wins" (SEC-024) made executable, proven by benchmark
  case S49;
- the **external-deletion judgement** — §25/§26's three answers, word for
  word the ones benchmark cases S55–S57 check;
- the **table-closure check** — §23's sweep refuses a table it has not been
  told about instead of walking past it.

Encoding conventions (the repository's own, quoted rather than invented):
fields join with US (ASCII 0x1f, ``elc.runtime.projections.SLICE_FIELD_
SEPARATOR``) so no field boundary can be forged by content; digests are
sha256; short ids keep 20 hex characters (the ``pj-`` / ``rm-`` / ``sv-``
deterministic-id convention).
"""

from __future__ import annotations

import hashlib
from typing import AbstractSet, Iterable, Mapping, Sequence

from elc.deletion.types import (
    GLOBAL_CONTENT_TABLES,
    RETAINED_TABLES,
    SWEPT_TABLES,
    ExternalAction,
    ExternalDeletionPlan,
    ExternalDisclosure,
    ExternalDisclosureStatus,
    RemoteRevocation,
)

__all__ = [
    "ENTITY_FIELD_SEPARATOR",
    "TOMBSTONE_ID_PREFIX",
    "UnknownTableError",
    "apply_tombstone_guard",
    "assert_known_tables",
    "entity_hash_for",
    "is_tombstoned",
    "plan_external_deletion",
    "tombstone_id_for",
]

#: Field separator for every digest this module derives. US is the
#: repository's unit-separator convention (elc/runtime/projections.py).
ENTITY_FIELD_SEPARATOR = "\x1f"

#: The ``ts-`` family beside the repository's ``pj-`` / ``rm-`` / ``an-`` /
#: ``sv-`` deterministic ids.
TOMBSTONE_ID_PREFIX = "ts-"

#: How many hex characters of the digest the short ids keep.
_DIGEST_CHARS = 20

#: The statuses §25 calls "NOT_SENT / QUEUED" — nothing has left the app, so
#: there is nothing to revoke.
_UNSENT_STATUSES = frozenset(
    {ExternalDisclosureStatus.NOT_SENT, ExternalDisclosureStatus.QUEUED}
)

#: The statuses §26 calls sent — the data is out of the app's boundary.
_SENT_STATUSES = frozenset(
    {
        ExternalDisclosureStatus.SENT,
        ExternalDisclosureStatus.SENT_COMPLETE,
        ExternalDisclosureStatus.SENT_PARTIAL,
    }
)


def entity_hash_for(entity_kind: str, entity_id: str) -> str:
    """§24's "opaque entity identity/hash": the one-way digest of one entity.

    ``sha256(entity_kind + US + entity_id).hexdigest()`` — the full 64 hex
    characters, because this value *is* the tombstone's identity and
    truncating it would only widen the accidental-collision surface for no
    storage win (the 20-character rule is for the short ``-`` ids, not for
    this column).

    The kind is inside the digest on purpose: an id that means one thing in
    one table and another thing in another table must not collide in the
    ledger, and the kind is the only thing that distinguishes them once the
    row is gone.

    Precondition (the repository's deterministic-id convention): the caller
    guarantees neither part carries US (0x1f). Both parts are a fixed table
    name and a store-minted opaque id, so no field boundary can be forged in
    practice; the encoding is a convention, not a defence, and does not claim
    to be one.
    """

    return hashlib.sha256(
        f"{entity_kind}{ENTITY_FIELD_SEPARATOR}{entity_id}".encode("utf-8")
    ).hexdigest()


def tombstone_id_for(entity_kind: str, entity_hash: str) -> str:
    """The ledger row's opaque primary key, derived rather than minted.

    ``ts-{sha256(entity_kind + US + entity_hash)[:20]}`` — the same shape the
    CP4 job id uses over its own pair. Deriving it from
    ``(entity_kind, entity_hash)`` is what makes the write idempotent: a
    second deletion of the same entity addresses the same row, and the unique
    index migration 0014 lands is the durable form of the same statement.
    """

    digest = hashlib.sha256(
        f"{entity_kind}{ENTITY_FIELD_SEPARATOR}{entity_hash}".encode("utf-8")
    ).hexdigest()
    return f"{TOMBSTONE_ID_PREFIX}{digest[:_DIGEST_CHARS]}"


def is_tombstoned(
    ledger: AbstractSet[tuple[str, str]],
    *,
    entity_kind: str,
    entity_id: str,
) -> bool:
    """SEC-024's predicate: is this entity already in the deletion ledger?

    ``ledger`` is the ``(entity_kind, entity_hash)`` set the durable read face
    returns (elc/deletion/queries.py). The *id* is hashed here rather than
    looked up, which is the whole point of §24's opaqueness: the ledger can
    answer the question without holding the id it is answering about.
    """

    return (entity_kind, entity_hash_for(entity_kind, entity_id)) in ledger


def apply_tombstone_guard(
    records: Sequence[Mapping[str, object]],
    *,
    ledger: AbstractSet[tuple[str, str]],
    entity_kind: str,
    id_field: str = "id",
) -> tuple[Mapping[str, object], ...]:
    """§24's "tombstone wins": drop every record the ledger has an entry for.

    Benchmark case S49 is this function, word for word:
    ``records=[{id: "old", data: "deleted"}, {id: "keep", data: "ok"}]`` with
    ``tombstones=["old"]`` keeps exactly ``["keep"]`` — a stale backup cannot
    silently resurrect a deleted entity.

    **V1 has no import/backup face** (§16's portable export / import is a
    later cut), so this is a guard with no shipped caller: it exists so that
    the semantics are executable and pinned now, and the day an import path
    lands it has one place to call instead of a paragraph to re-read. The
    absence of the import face is registered rather than papered over — a
    test asserts both the guard's behaviour and that no module outside this
    package imports it.
    """

    return tuple(
        record
        for record in records
        if not is_tombstoned(
            ledger,
            entity_kind=entity_kind,
            entity_id=str(record[id_field]),
        )
    )


def plan_external_deletion(
    disclosure: ExternalDisclosure,
) -> ExternalDeletionPlan:
    """§25/§26's judgement over one disclosure — the three benchmark answers.

    Verbatim the reference implementation's
    (``security_reference_v1.plan_external_disclosure_deletion``, the
    function benchmark cases S55–S57 exercise), so this face and the
    baseline agree by construction:

    - ``NOT_SENT`` / ``QUEUED`` → ``NONE`` / ``NOT_APPLICABLE``
      (§25 "cancel before transmission"; nothing was disclosed);
    - ``SENT*`` without both a supported provider delete *and* an identifier →
      ``NONE`` / ``CANNOT_BE_GUARANTEED_BY_APP`` (§26's "Provider 不支持或无法
      定位 ⇒ remote revocation cannot be guaranteed by this app", and §26's
      ban on claiming "已从所有模型服务商永久删除");
    - ``SENT*`` with both → ``SCHEDULE_PROVIDER_DELETE`` /
      ``PENDING_PROVIDER`` (§26's "schedule provider delete / mark remote
      revocation pending").

    **No remote call is made, in this cut or in V1.** The third branch names
    an intent the app will carry; the durable trace of a real transmission is
    ``provider_attempt.provider_request_id``, and the caller that would act on
    this plan does not exist yet (there is no external provider wired). The
    judgement is what the benchmark pins, and it is honest about being a
    judgement: ``PENDING_PROVIDER`` says pending, never done.
    """

    if disclosure.status in _UNSENT_STATUSES:
        return ExternalDeletionPlan(
            external_action=ExternalAction.NONE,
            remote_revocation=RemoteRevocation.NOT_APPLICABLE,
        )
    if disclosure.status in _SENT_STATUSES:
        if disclosure.provider_delete_supported and (
            disclosure.provider_request_identifier
        ):
            return ExternalDeletionPlan(
                external_action=ExternalAction.SCHEDULE_PROVIDER_DELETE,
                remote_revocation=RemoteRevocation.PENDING_PROVIDER,
            )
        return ExternalDeletionPlan(
            external_action=ExternalAction.NONE,
            remote_revocation=RemoteRevocation.CANNOT_BE_GUARANTEED_BY_APP,
        )
    # Defensive only: the vocabulary is closed, so a caller cannot reach this
    # arm through the enum. Saying UNKNOWN rather than guessing ALLOW is
    # SEC-029's rule ("Security UNKNOWN is not treated as ALLOW") applied to
    # the one place a future word could arrive from.
    return ExternalDeletionPlan(
        external_action=ExternalAction.NONE,
        remote_revocation=RemoteRevocation.UNKNOWN,
    )


class UnknownTableError(RuntimeError):
    """The database carries a table none of the three sets claims.

    Raised rather than skipped: §23 deletes "all user canonical records / all
    user-derived records" and the only way to keep that true as the schema
    grows is to refuse the sweep the moment a table appears that no one has
    classified (elc/deletion/types.py's module docstring).
    """

    def __init__(self, tables: Iterable[str]) -> None:
        self.tables = tuple(sorted(tables))
        super().__init__(
            "app.db carries table(s) this package has not classified: "
            + ", ".join(self.tables)
            + " — add each one to elc.deletion.types' SWEPT_TABLES or"
            " RETAINED_TABLES (a global content table would go to"
            " GLOBAL_CONTENT_TABLES) before the sweep may run"
        )


def assert_known_tables(tables: Iterable[str]) -> None:
    """Refuse a database that carries an unclassified table (§23).

    The three sets partition every table of a freshly migrated app.db; this
    function is the runtime half of that statement (the test side holds the
    same three sets against the real schema).
    """

    known = set(SWEPT_TABLES) | set(RETAINED_TABLES) | set(GLOBAL_CONTENT_TABLES)
    unknown = [table for table in tables if table not in known]
    if unknown:
        raise UnknownTableError(unknown)
