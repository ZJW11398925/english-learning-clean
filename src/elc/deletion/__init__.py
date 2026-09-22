"""Deletion / Tombstone bounded context (BF-05; IP §16 DoD #25).

The module that answers "what happens to everything derived from this?" —
source-aware deletion over docs/DATA_MODEL.md §24.14's "长期 private/derived
records 必须保留 provenance/source ids，支持 source-aware deletion/rebuild"
and behavioral_baselines/security/SECURITY_PRIVACY_DELETION_CONTRACT_v1.0.md
§17–§28 (SEC-017…SEC-028), proven by the contract's own executable benchmark
(security_benchmark_v1.json cases S41–S49 and S55–S57).

Layout, the repository's usual four faces plus the pure policy module:

    types.py       the scope vocabulary, the request/outcome records, the
                   app.db table sets the sweep is defined over
    plan.py        the pure derivations: tombstone identity, the §24
                   predicate and import guard, the §25/§26 judgement, the
                   §23 unknown-table refusal
    store.py       every statement (SQL lives here and nowhere else)
    controller.py  the authority face; rebuilds through the existing
                   LearnerState / schedule / CP4-episode faces
    commands.py    the write protocol
    queries.py     the read protocol

What this package does **not** claim (registered, not glossed):

- no import or backup face exists in V1 (§16's portable export/import is a
  later cut), so §24's "tombstone wins" ships as an executable predicate and
  guard with no production caller;
- no remote provider call is ever made: §26's three answers are a judgement
  (``plan_external_deletion``), and the SENT branch says PENDING, never done;
- no retrieval-index or embedding store exists in V1, so §18's "indexes /
  embeddings deleted or rebuilt" has no storage to act on;
- no persona definition table exists in app.db, so §22's PERSONA_PACKAGE
  scope has an empty app.db surface by construction;
- ``user_profile`` has no per-fact provenance column (§17 asks for one, §5.1
  freezes the column set), so the benchmark's PROFILE_FIELD scope is
  fail-closed: the whole ``profile_facts`` set is removed rather than
  guessing which entry the caller named.
"""

from elc.deletion.commands import DeletionCommands
from elc.deletion.controller import (
    DeletionController,
    LearnerStateRebuildPort,
    ProjectionRebuildPort,
    ScheduleRecomputePort,
)
from elc.deletion.plan import (
    ENTITY_FIELD_SEPARATOR,
    TOMBSTONE_ID_PREFIX,
    UnknownTableError,
    apply_tombstone_guard,
    assert_known_tables,
    entity_hash_for,
    is_tombstoned,
    plan_external_deletion,
    tombstone_id_for,
)
from elc.deletion.queries import DeletionQueries
from elc.deletion.store import (
    TOMBSTONE_TABLE,
    SqliteDeletionStore,
    StaleDeletionStoreError,
)
from elc.deletion.types import (
    ALL_USER_DATA_SWEPT_TABLES,
    DELETION_POLICY_VERSION,
    GLOBAL_CONTENT_TABLES,
    PROFILE_FIELD_ENTITY_KIND,
    RETAINED_TABLES,
    SCOPE_SWEPT_TABLES,
    SWEPT_TABLES,
    DeletionExecution,
    DeletionOutcome,
    DeletionRequest,
    DeletionScope,
    EpisodeRebuildKey,
    ExternalAction,
    ExternalDeletionPlan,
    ExternalDisclosure,
    ExternalDisclosureStatus,
    RebuildAttempt,
    RemoteRevocation,
    TableTally,
    TargetKey,
    TombstoneRecord,
)

__all__ = [
    "ALL_USER_DATA_SWEPT_TABLES",
    "DELETION_POLICY_VERSION",
    "ENTITY_FIELD_SEPARATOR",
    "GLOBAL_CONTENT_TABLES",
    "PROFILE_FIELD_ENTITY_KIND",
    "RETAINED_TABLES",
    "SCOPE_SWEPT_TABLES",
    "SWEPT_TABLES",
    "TOMBSTONE_ID_PREFIX",
    "TOMBSTONE_TABLE",
    "DeletionCommands",
    "DeletionController",
    "DeletionExecution",
    "DeletionOutcome",
    "DeletionQueries",
    "DeletionRequest",
    "DeletionScope",
    "EpisodeRebuildKey",
    "ExternalAction",
    "ExternalDeletionPlan",
    "ExternalDisclosure",
    "ExternalDisclosureStatus",
    "LearnerStateRebuildPort",
    "ProjectionRebuildPort",
    "RebuildAttempt",
    "RemoteRevocation",
    "ScheduleRecomputePort",
    "SqliteDeletionStore",
    "StaleDeletionStoreError",
    "TableTally",
    "TargetKey",
    "TombstoneRecord",
    "UnknownTableError",
    "apply_tombstone_guard",
    "assert_known_tables",
    "entity_hash_for",
    "is_tombstoned",
    "plan_external_deletion",
    "tombstone_id_for",
]
